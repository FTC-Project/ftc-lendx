from __future__ import annotations

from typing import Dict, Optional
from celery import shared_task
from decimal import Decimal

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.flow import (
    start_flow,
    set_step,
    clear_flow,
    mark_prev_keyboard,
    reply,
)
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register

from backend.apps.users.models import TelegramUser
from backend.apps.users.crypto import decrypt_secret
from backend.apps.tokens.services.ftc_token import FTCTokenService
from django.conf import settings

import logging

logger = logging.getLogger(__name__)

# Command + steps
CMD = "buyftc"

# Flow steps
S_CHECK_BALANCE = "check_xrp_balance"
S_SELECT_AMOUNT = "select_amount"
S_ENTER_CUSTOM = "enter_custom_amount"
S_CONFIRM_PURCHASE = "confirm_purchase"
S_PROCESSING = "processing"


# ---------------------------
# Keyboard helpers
# ---------------------------


def kb_amount_selection() -> dict:
    """Keyboard for selecting FTC amount to buy."""
    return {
        "inline_keyboard": [
            [
                {"text": "100 FTC", "callback_data": "buyftc:amount:100"},
                {"text": "200 FTC", "callback_data": "buyftc:amount:200"},
            ],
            [
                {"text": "500 FTC", "callback_data": "buyftc:amount:500"},
                {"text": "🔢 Custom Amount", "callback_data": "buyftc:amount:custom"},
            ],
            [{"text": "❌ Cancel", "callback_data": "flow:cancel"}],
        ]
    }


def kb_confirm_purchase(amount: float, xrp_cost: float) -> dict:
    """Keyboard to confirm purchase."""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Confirm Purchase", "callback_data": "buyftc:confirm:yes"},
                {"text": "❌ Cancel", "callback_data": "buyftc:confirm:no"},
            ],
        ]
    }


# ---------------------------
# BuyFTCCommand
# ---------------------------


@register(
    name=CMD,
    aliases=["/buyftc"],
    description="Buy FTC tokens with XRP",
    permission="public",
)
class BuyFTCCommand(BaseCommand):
    name = CMD
    description = "Buy FTC tokens with XRP"
    permission = "public"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(msg.chat_id)

        # Start flow
        if not state:
            data = {}

            # Check if user is KYC verified
            try:
                user = TelegramUser.objects.get(telegram_id=msg.user_id)

                # Check if user has KYC record and is verified
                if not hasattr(user, "kyc") or user.kyc.status != "verified":
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ <b>KYC Verification Required</b>\n\n"
                        "You must complete KYC verification before buying FTC tokens.\n\n"
                        "Please use /register to complete your KYC verification.",
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                # Check if user has wallet
                if not hasattr(user, "wallet") or not user.wallet:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ <b>No Wallet Found</b>\n\n"
                        "You don't have a wallet yet. Please complete registration first.",
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                wallet_address = user.wallet.address

                # Initialize FTC service
                ftc_service = FTCTokenService()

                # Check user's XRP balance
                xrp_balance_wei = ftc_service.web3.eth.get_balance(wallet_address)
                xrp_balance = float(ftc_service.web3.from_wei(xrp_balance_wei, "ether"))

                # Store wallet info in data
                data["wallet_address"] = wallet_address
                data["xrp_balance"] = xrp_balance

                # If user has no or very low XRP, send them test XRP
                if xrp_balance < 1.0:
                    start_flow(fsm, msg.chat_id, CMD, data, S_CHECK_BALANCE)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        f"💰 <b>Welcome to FTC Token Purchase</b>\n\n"
                        f"Your wallet: <code>{wallet_address}</code>\n"
                        f"Current XRP balance: {xrp_balance:.4f} XRP\n\n"
                        f"⚠️ <b>Low XRP Balance Detected</b>\n\n"
                        f"You need XRP to purchase FTC tokens and pay for gas fees.\n\n"
                        f"🎁 <b>For testing purposes</b>, we'll send you 5 XRP.\n"
                        f"<i>In production, you would need to purchase XRP yourself.</i>\n\n"
                        f"Sending you 5 XRP now...",
                        data=data,
                        parse_mode="HTML",
                    )

                    # Send test XRP from admin wallet
                    try:
                        admin_account = ftc_service.get_account_from_private_key(
                            settings.ADMIN_PRIVATE_KEY
                        )
                        gas_amount = ftc_service.web3.to_wei(5, "ether")

                        tx = {
                            "from": settings.ADMIN_ADDRESS,
                            "to": wallet_address,
                            "value": gas_amount,
                            "gas": 21000,
                            "gasPrice": ftc_service.web3.eth.gas_price,
                            "nonce": ftc_service.web3.eth.get_transaction_count(
                                settings.ADMIN_ADDRESS
                            ),
                            "chainId": ftc_service.web3.eth.chain_id,
                        }

                        signed_tx = admin_account.sign_transaction(tx)
                        tx_hash = ftc_service.web3.eth.send_raw_transaction(
                            signed_tx.raw_transaction
                        )
                        receipt = ftc_service.web3.eth.wait_for_transaction_receipt(
                            tx_hash, timeout=120
                        )

                        # Update balance
                        new_xrp_balance_wei = ftc_service.web3.eth.get_balance(
                            wallet_address
                        )
                        new_xrp_balance = float(
                            ftc_service.web3.from_wei(new_xrp_balance_wei, "ether")
                        )
                        data["xrp_balance"] = new_xrp_balance

                        # Move to amount selection
                        set_step(fsm, msg.chat_id, CMD, S_SELECT_AMOUNT, data)
                        mark_prev_keyboard(data, msg)
                        reply(
                            msg,
                            f"✅ <b>XRP Sent Successfully!</b>\n\n"
                            f"Transaction: <code>{tx_hash.hex()[:16]}...</code>\n"
                            f"New XRP balance: {new_xrp_balance:.4f} XRP\n\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"<b>How much FTC would you like to buy?</b>\n\n"
                            f"<i>Exchange rate: 1 FTC = 0.01 XRP (for testing)</i>",
                            kb_amount_selection(),
                            data=data,
                            parse_mode="HTML",
                        )
                        return

                    except Exception as e:
                        logger.error(
                            f"[BuyFTC] Failed to send test XRP: {e}", exc_info=True
                        )
                        mark_prev_keyboard(data, msg)
                        reply(
                            msg,
                            f"❌ <b>Failed to Send Test XRP</b>\n\n"
                            f"Error: {str(e)}\n\n"
                            f"Please ensure your blockchain is running.",
                            data=data,
                            parse_mode="HTML",
                        )
                        return

                # User has sufficient XRP, proceed to amount selection
                start_flow(fsm, msg.chat_id, CMD, data, S_SELECT_AMOUNT)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    f"💰 <b>Welcome to FTC Token Purchase</b>\n\n"
                    f"Your wallet: <code>{wallet_address}</code>\n"
                    f"XRP balance: {xrp_balance:.4f} XRP\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"<b>How much FTC would you like to buy?</b>\n\n"
                    f"<i>Exchange rate: 1 FTC = 0.01 XRP (for testing)</i>",
                    kb_amount_selection(),
                    data=data,
                    parse_mode="HTML",
                )
                return

            except TelegramUser.DoesNotExist:
                logger.error(f"User not found: {msg.user_id}")
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ <b>User Not Found</b>\n\n" "Please register first using /start",
                    data=data,
                    parse_mode="HTML",
                )
                return
            except Exception as e:
                logger.error(f"[BuyFTC] Error starting flow: {e}", exc_info=True)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    f"❌ <b>Error</b>\n\n{str(e)}",
                    data=data,
                    parse_mode="HTML",
                )
                return

        # Guard: only handle our own flow
        if state.get("command") != CMD:
            return

        step = state.get("step") or S_SELECT_AMOUNT
        data = state.get("data", {}) or {}
        cb = getattr(msg, "callback_data", None)
        text = (msg.text or "").strip()

        # Handle cancel
        if cb == "flow:cancel" or cb == "buyftc:confirm:no":
            clear_flow(fsm, msg.chat_id)
            mark_prev_keyboard(data, msg)
            reply(msg, "❌ Purchase cancelled. Use /buyftc to start again.", data=data)
            return

        # Handle amount selection
        if step == S_SELECT_AMOUNT and cb and cb.startswith("buyftc:amount:"):
            amount_str = cb.split("buyftc:amount:", 1)[1]

            if amount_str == "custom":
                # Ask user to enter custom amount
                set_step(fsm, msg.chat_id, CMD, S_ENTER_CUSTOM, data)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "🔢 <b>Enter Custom Amount</b>\n\n"
                    "Please enter the amount of FTC you want to buy.\n\n"
                    "📊 <b>Valid range:</b> 1 - 300 FTC\n\n"
                    "<i>Type a number and send it.</i>",
                    {
                        "inline_keyboard": [
                            [{"text": "❌ Cancel", "callback_data": "flow:cancel"}]
                        ]
                    },
                    data=data,
                    parse_mode="HTML",
                )
                return
            else:
                # Pre-selected amount
                try:
                    amount = float(amount_str)
                    data["ftc_amount"] = amount
                    xrp_cost = amount * 0.01  # 1 FTC = 0.01 XRP
                    data["xrp_cost"] = xrp_cost

                    # Check if user has enough XRP
                    xrp_balance = data.get("xrp_balance", 0)
                    if xrp_balance < xrp_cost:
                        mark_prev_keyboard(data, msg)
                        reply(
                            msg,
                            f"❌ <b>Insufficient XRP Balance</b>\n\n"
                            f"You need {xrp_cost:.4f} XRP to buy {amount:,.0f} FTC.\n"
                            f"Your balance: {xrp_balance:.4f} XRP\n\n"
                            f"Please select a smaller amount.",
                            kb_amount_selection(),
                            data=data,
                            parse_mode="HTML",
                        )
                        return

                    # Move to confirmation
                    set_step(fsm, msg.chat_id, CMD, S_CONFIRM_PURCHASE, data)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        f"🔍 <b>Confirm Purchase</b>\n\n"
                        f"<b>You will receive:</b> {amount:,.0f} FTC\n"
                        f"<b>You will pay:</b> {xrp_cost:.4f} XRP\n\n"
                        f"<b>Your balances after purchase:</b>\n"
                        f"💵 XRP: {xrp_balance - xrp_cost:.4f} XRP\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<i>Please confirm to proceed with the purchase.</i>",
                        kb_confirm_purchase(amount, xrp_cost),
                        data=data,
                        parse_mode="HTML",
                    )
                    return
                except ValueError:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ Invalid amount. Please try again.",
                        kb_amount_selection(),
                        data=data,
                    )
                    return

        # Handle custom amount input
        if step == S_ENTER_CUSTOM and text:
            try:
                amount = float(text)

                # Validate range
                if amount < 1 or amount > 300:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        f"❌ <b>Invalid Amount</b>\n\n"
                        f"You entered: {amount}\n\n"
                        f"Please enter a number between 1 and 300.",
                        {
                            "inline_keyboard": [
                                [{"text": "❌ Cancel", "callback_data": "flow:cancel"}]
                            ]
                        },
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                data["ftc_amount"] = amount
                xrp_cost = amount * 0.01  # 1 FTC = 0.01 XRP
                data["xrp_cost"] = xrp_cost

                # Check if user has enough XRP
                xrp_balance = data.get("xrp_balance", 0)
                if xrp_balance < xrp_cost:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        f"❌ <b>Insufficient XRP Balance</b>\n\n"
                        f"You need {xrp_cost:.4f} XRP to buy {amount:,.0f} FTC.\n"
                        f"Your balance: {xrp_balance:.4f} XRP\n\n"
                        f"Please enter a smaller amount.",
                        {
                            "inline_keyboard": [
                                [{"text": "❌ Cancel", "callback_data": "flow:cancel"}]
                            ]
                        },
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                # Move to confirmation
                set_step(fsm, msg.chat_id, CMD, S_CONFIRM_PURCHASE, data)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    f"🔍 <b>Confirm Purchase</b>\n\n"
                    f"<b>You will receive:</b> {amount:,.0f} FTC\n"
                    f"<b>You will pay:</b> {xrp_cost:.4f} XRP\n\n"
                    f"<b>Your balances after purchase:</b>\n"
                    f"💵 XRP: {xrp_balance - xrp_cost:.4f} XRP\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"<i>Please confirm to proceed with the purchase.</i>",
                    kb_confirm_purchase(amount, xrp_cost),
                    data=data,
                    parse_mode="HTML",
                )
                return

            except ValueError:
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ <b>Invalid Input</b>\n\n"
                    "Please enter a valid number between 1 and 300.",
                    {
                        "inline_keyboard": [
                            [{"text": "❌ Cancel", "callback_data": "flow:cancel"}]
                        ]
                    },
                    data=data,
                    parse_mode="HTML",
                )
                return

        # Handle purchase confirmation
        if step == S_CONFIRM_PURCHASE and cb == "buyftc:confirm:yes":
            try:
                user = TelegramUser.objects.get(telegram_id=msg.user_id)
                wallet_address = data["wallet_address"]
                ftc_amount = data["ftc_amount"]
                xrp_cost = data["xrp_cost"]

                # Decrypt user's private key
                user_private_key = decrypt_secret(user.wallet.secret_encrypted)

                set_step(fsm, msg.chat_id, CMD, S_PROCESSING, data)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    f"⏳ <b>Processing Purchase...</b>\n\n"
                    f"Please wait while we:\n"
                    f"1️⃣ Transfer {xrp_cost:.4f} XRP from your wallet to admin\n"
                    f"2️⃣ Mint {ftc_amount:,.0f} FTC to your wallet\n\n"
                    f"<i>This may take a few moments...</i>",
                    data=data,
                    parse_mode="HTML",
                )

                # Initialize service
                ftc_service = FTCTokenService()

                # STEP 1: User sends XRP to admin
                logger.info(
                    f"[BuyFTC] User {wallet_address} sending {xrp_cost} XRP to admin"
                )
                user_account = ftc_service.get_account_from_private_key(
                    user_private_key
                )

                xrp_transfer_tx = {
                    "from": wallet_address,
                    "to": settings.ADMIN_ADDRESS,
                    "value": ftc_service.web3.to_wei(xrp_cost, "ether"),
                    "gas": 21000,
                    "gasPrice": ftc_service.web3.eth.gas_price,
                    "nonce": ftc_service.web3.eth.get_transaction_count(wallet_address),
                    "chainId": ftc_service.web3.eth.chain_id,
                }

                signed_xrp_tx = user_account.sign_transaction(xrp_transfer_tx)
                xrp_tx_hash = ftc_service.web3.eth.send_raw_transaction(
                    signed_xrp_tx.raw_transaction
                )
                xrp_receipt = ftc_service.web3.eth.wait_for_transaction_receipt(
                    xrp_tx_hash, timeout=120
                )
                logger.info(f"[BuyFTC] XRP transfer: {xrp_tx_hash.hex()}")

                # STEP 2: Admin mints FTC to user
                logger.info(f"[BuyFTC] Minting {ftc_amount} FTC to {wallet_address}")
                mint_result = ftc_service.mint(
                    to_address=wallet_address,
                    amount=ftc_amount,
                )
                logger.info(f"[BuyFTC] Minted: {mint_result['tx_hash']}")

                # Get updated balances
                ftc_balance = ftc_service.get_balance(wallet_address)
                xrp_balance_wei = ftc_service.web3.eth.get_balance(wallet_address)
                xrp_balance = float(ftc_service.web3.from_wei(xrp_balance_wei, "ether"))

                # Success message
                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    f"✅ <b>Purchase Successful!</b>\n\n"
                    f"<b>Wallet:</b> <code>{wallet_address}</code>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"<b>Transactions:</b>\n"
                    f"1️⃣ XRP Payment: <code>{xrp_tx_hash.hex()[:16]}...</code>\n"
                    f"2️⃣ FTC Mint: <code>{mint_result['tx_hash'][:16]}...</code>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"<b>Your New Balances:</b>\n"
                    f"💵 FTC: {ftc_balance:,.2f} FTC\n"
                    f"⛽ XRP: {xrp_balance:.4f} XRP\n\n"
                    f"<i>Thank you for your purchase! You received {ftc_amount:,.0f} FTC tokens.</i>",
                    data=data,
                    parse_mode="HTML",
                )
                return

            except Exception as e:
                logger.error(f"[BuyFTC] Error during purchase: {e}", exc_info=True)
                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    f"❌ <b>Purchase Failed</b>\n\n"
                    f"Something went wrong during the purchase.\n\n"
                    f"<i>Error: {str(e)}</i>\n\n"
                    f"Your XRP has not been transferred. Please try again.",
                    data=data,
                    parse_mode="HTML",
                )
                return

        # Fallback for unexpected input
        if step == S_SELECT_AMOUNT:
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "Please select an amount using the buttons below.",
                kb_amount_selection(),
                data=data,
            )
            return

        if step == S_CONFIRM_PURCHASE:
            mark_prev_keyboard(data, msg)
            ftc_amount = data.get("ftc_amount", 0)
            xrp_cost = data.get("xrp_cost", 0)
            reply(
                msg,
                f"🔍 <b>Confirm Purchase</b>\n\n"
                f"<b>You will receive:</b> {ftc_amount:,.0f} FTC\n"
                f"<b>You will pay:</b> {xrp_cost:.4f} XRP\n\n"
                f"Please use the buttons to confirm or cancel.",
                kb_confirm_purchase(ftc_amount, xrp_cost),
                data=data,
                parse_mode="HTML",
            )
            return

        # Final fallback → reset
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please use /buyftc to start again.")
