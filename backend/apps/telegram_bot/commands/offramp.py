from __future__ import annotations

from typing import Dict, Optional
from celery import shared_task
from decimal import Decimal

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.flow import (
    start_flow,
    set_step,
    clear_flow,
    prev_step_of,
    mark_prev_keyboard,
    reply,
)
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.keyboards import kb_back_cancel, kb_confirm

from backend.apps.users.models import TelegramUser
from backend.apps.users.crypto import decrypt_secret
from backend.apps.tokens.services.ftc_token import FTCTokenService
from django.conf import settings

import logging

logger = logging.getLogger(__name__)

# Command + steps
CMD = "offramp"

# Flow steps
S_SELECT_AMOUNT = "select_amount"
S_ENTER_CUSTOM = "enter_custom_amount"
S_CONFIRM_OFFRAMP = "confirm_offramp"
S_PROCESSING = "processing"

PREV: Dict[str, Optional[str]] = {
    S_SELECT_AMOUNT: None,
    S_ENTER_CUSTOM: S_SELECT_AMOUNT,
    S_CONFIRM_OFFRAMP: S_SELECT_AMOUNT,
    S_PROCESSING: S_CONFIRM_OFFRAMP,
}


# ---------------------------
# Keyboard helpers
# ---------------------------


def kb_amount_selection() -> dict:
    """Keyboard for selecting FTC amount to off-ramp."""
    return {
        "inline_keyboard": [
            [
                {"text": "100 FTC", "callback_data": "offramp:amount:100"},
                {"text": "200 FTC", "callback_data": "offramp:amount:200"},
            ],
            [
                {"text": "500 FTC", "callback_data": "offramp:amount:500"},
                {"text": "1000 FTC", "callback_data": "offramp:amount:1000"},
            ],
            [
                {"text": "🔢 Custom Amount", "callback_data": "offramp:amount:custom"},
                {"text": "💰 All Balance", "callback_data": "offramp:amount:all"},
            ],
            [{"text": "❌ Cancel", "callback_data": "flow:cancel"}],
        ]
    }


# ---------------------------
# Helper functions
# ---------------------------


def _fmt_ftc(amount: float) -> str:
    """Format FTC amount."""
    return f"{amount:,.2f} FTC"


# ---------------------------
# OfframpCommand
# ---------------------------


@register(
    name=CMD,
    aliases=["/offramp"],
    description="Convert FTC tokens to ZAR (off-ramp)",
    permission="verified_borrower",
)
class OfframpCommand(BaseCommand):
    name = CMD
    description = "Convert FTC tokens to ZAR (off-ramp)"
    permission = "verified_borrower"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(msg.chat_id)

        # Start flow
        if not state:
            try:
                user = TelegramUser.objects.get(telegram_id=msg.user_id)

                # Check if user has wallet
                if not hasattr(user, "wallet") or not user.wallet:
                    mark_prev_keyboard({}, msg)
                    reply(
                        msg,
                        "❌ <b>No Wallet Found</b>\n\n"
                        "You don't have a wallet configured.\n\n"
                        "Please contact support to set up your wallet.",
                        parse_mode="HTML",
                    )
                    return

                # Get FTC balance
                wallet_address = user.wallet.address
                ftc_service = FTCTokenService()
                ftc_balance = ftc_service.get_balance(wallet_address)

                if ftc_balance <= 0:
                    mark_prev_keyboard({}, msg)
                    reply(
                        msg,
                        "💸 <b>No FTC Balance</b>\n\n"
                        "You don't have any FTC tokens to off-ramp.\n\n"
                        "Use /buyftc to purchase FTC tokens first.",
                        parse_mode="HTML",
                    )
                    return

                # Start flow with balance data
                data = {
                    "ftc_balance": float(ftc_balance),
                }
                start_flow(fsm, msg.chat_id, CMD, data, S_SELECT_AMOUNT)

                # Show welcome message with balance
                welcome_msg = (
                    "💱 <b>Off-Ramp FTC to ZAR</b>\n\n"
                    f"<b>Your FTC Balance:</b> {_fmt_ftc(float(ftc_balance))}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "<b>How much FTC would you like to convert?</b>\n\n"
                    "<i>💡 Exchange Rate: 1 FTC = R1.00</i>\n\n"
                    "<b>⚠️ MVP Notice:</b>\n"
                    "<i>In production, this would transfer funds to your bank account via an exchange. "
                    "For this MVP, we'll burn the FTC tokens to simulate the off-ramp process.</i>"
                )

                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    welcome_msg,
                    kb_amount_selection(),
                    data=data,
                    parse_mode="HTML",
                )
                return

            except TelegramUser.DoesNotExist:
                mark_prev_keyboard({}, msg)
                reply(
                    msg,
                    "❌ <b>User Not Found</b>\n\n"
                    "Please use /start to register first.",
                    parse_mode="HTML",
                )
                return
            except Exception as e:
                logger.error(f"[Offramp] Error starting flow: {e}", exc_info=True)
                mark_prev_keyboard({}, msg)
                reply(
                    msg,
                    "❌ <b>Error</b>\n\n"
                    f"An error occurred: {str(e)}\n\n"
                    "Please try again or contact support.",
                    parse_mode="HTML",
                )
                return

        # Guard: other command owns this chat
        if state.get("command") != CMD:
            return

        step = state.get("step")
        data = state.get("data", {}) or {}

        # --- Callbacks ---
        cb = getattr(msg, "callback_data", None)
        if cb:
            if cb == "flow:cancel":
                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ <b>Off-Ramp Cancelled</b>\n\n"
                    "Your off-ramp request has been cancelled.\n\n"
                    "Use /offramp to try again.",
                    data=data,
                    parse_mode="HTML",
                )
                return

            if cb == "flow:back":
                prev = prev_step_of(PREV, step)
                if prev is None:
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "👋 <b>Exiting Off-Ramp</b>\n\n" "Off-ramp cancelled.",
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                set_step(fsm, msg.chat_id, CMD, prev, data)

                if prev == S_SELECT_AMOUNT:
                    welcome_msg = (
                        "💱 <b>Off-Ramp FTC to ZAR</b>\n\n"
                        f"<b>Your FTC Balance:</b> {_fmt_ftc(data['ftc_balance'])}\n\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "<b>How much FTC would you like to convert?</b>\n\n"
                        "<i>💡 Exchange Rate: 1 FTC = R1.00</i>\n\n"
                        "<b>⚠️ MVP Notice:</b>\n"
                        "<i>In production, this would transfer funds to your bank account via an exchange. "
                        "For this MVP, we'll burn the FTC tokens to simulate the off-ramp process.</i>"
                    )
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        welcome_msg,
                        kb_amount_selection(),
                        data=data,
                        parse_mode="HTML",
                    )
                return

            # Amount selection
            if step == S_SELECT_AMOUNT and cb.startswith("offramp:amount:"):
                amount_str = cb.split("offramp:amount:")[1]

                if amount_str == "custom":
                    set_step(fsm, msg.chat_id, CMD, S_ENTER_CUSTOM, data)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "🔢 <b>Custom Amount</b>\n\n"
                        f"<b>Your FTC Balance:</b> {_fmt_ftc(data['ftc_balance'])}\n\n"
                        "Please enter the amount of FTC you'd like to off-ramp:\n\n"
                        "<i>Example: 150</i>",
                        kb_back_cancel(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return
                elif amount_str == "all":
                    amount = data["ftc_balance"]
                else:
                    amount = float(amount_str)

                # Validate amount
                if amount <= 0:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ <b>Invalid Amount</b>\n\n"
                        "Please select a valid amount greater than 0.",
                        kb_amount_selection(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                if amount > data["ftc_balance"]:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ <b>Insufficient Balance</b>\n\n"
                        f"<b>Requested:</b> {_fmt_ftc(amount)}\n"
                        f"<b>Available:</b> {_fmt_ftc(data['ftc_balance'])}\n\n"
                        "Please select a lower amount.",
                        kb_amount_selection(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                # Store amount and move to confirmation
                data["amount"] = amount
                data["zar_equivalent"] = amount  # 1:1 conversion
                set_step(fsm, msg.chat_id, CMD, S_CONFIRM_OFFRAMP, data)

                confirmation_msg = (
                    "💱 <b>Off-Ramp Confirmation</b>\n\n"
                    f"<b>Amount to Off-Ramp:</b> {_fmt_ftc(amount)}\n"
                    f"<b>ZAR Equivalent:</b> R{amount:,.2f}\n"
                    f"<b>Remaining Balance:</b> {_fmt_ftc(data['ftc_balance'] - amount)}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "<b>⚠️ MVP Notice:</b>\n"
                    "<i>In a production environment, R{amount:,.2f} would be transferred to your "
                    "bank account via an exchange partner. For this MVP demonstration, we'll burn "
                    "the FTC tokens to simulate the off-ramp process.</i>\n\n"
                    "Confirm to proceed?"
                )

                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    confirmation_msg,
                    kb_confirm(),
                    data=data,
                    parse_mode="HTML",
                )
                return

            # Confirm off-ramp
            if step == S_CONFIRM_OFFRAMP and cb == "flow:confirm":
                try:
                    user = TelegramUser.objects.get(telegram_id=msg.user_id)
                    wallet_address = user.wallet.address
                    user_private_key = decrypt_secret(user.wallet.secret_encrypted)

                    amount = data["amount"]

                    set_step(fsm, msg.chat_id, CMD, S_PROCESSING, data)

                    # Show processing message
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "⏳ <b>Processing Off-Ramp...</b>\n\n"
                        f"Transferring {_fmt_ftc(amount)} to off-ramp wallet...\n\n"
                        "<i>Please wait...</i>",
                        data=data,
                        parse_mode="HTML",
                    )

                    # Transfer FTC tokens to dummy "burn" wallet
                    # In production, this would go to an exchange wallet
                    ftc_service = FTCTokenService()
                    burn_wallet = (
                        settings.BURN_WALLET_ADDRESS
                    )  # Dummy wallet for off-ramped tokens

                    logger.info(
                        f"[Offramp] Transferring {amount} FTC from user {user.telegram_id} to burn wallet"
                    )
                    burn_result = ftc_service.transfer(
                        from_address=wallet_address,
                        to_address=burn_wallet,
                        amount=amount,
                        private_key=user_private_key,
                    )
                    logger.info(
                        f"[Offramp] Transferred {amount} FTC to burn wallet, tx: {burn_result['tx_hash']}"
                    )

                    # Get new balance
                    new_balance = ftc_service.get_balance(wallet_address)

                    # Success message
                    success_msg = (
                        "✅ <b>Off-Ramp Successful!</b>\n\n"
                        f"<b>FTC Off-Ramped:</b> {_fmt_ftc(amount)}\n"
                        f"<b>ZAR Equivalent:</b> R{amount:,.2f}\n"
                        f"<b>New Balance:</b> {_fmt_ftc(float(new_balance))}\n\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<b>Transaction:</b> <code>{burn_result['tx_hash'][:16]}...</code>\n\n"
                        "<b>💡 Production Note:</b>\n"
                        f"<i>In a real-world scenario, your {_fmt_ftc(amount)} would be sent to an exchange "
                        "partner, converted to ZAR at market rate, and R{amount:,.2f} would be transferred "
                        "to your linked bank account within 1-2 business days. For this MVP, the tokens have "
                        "been transferred to a designated off-ramp wallet.</i>\n\n"
                        "Use /balance to view your updated wallet balance."
                    )

                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        success_msg,
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                except Exception as e:
                    logger.error(
                        f"[Offramp] Error processing off-ramp: {e}", exc_info=True
                    )
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ <b>Off-Ramp Failed</b>\n\n"
                        "An error occurred while processing your off-ramp.\n\n"
                        f"<i>Error: {str(e)}</i>\n\n"
                        "Please try again or contact support.",
                        data=data,
                        parse_mode="HTML",
                    )
                    return

            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "⚠️ <i>Unsupported action. Please use the buttons.</i>",
                data=data,
                parse_mode="HTML",
            )
            return

        # Text input handling
        text = (msg.text or "").strip()

        if step == S_ENTER_CUSTOM:
            try:
                amount = float(text)

                if amount <= 0:
                    raise ValueError("Amount must be greater than 0")

                if amount > data["ftc_balance"]:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ <b>Insufficient Balance</b>\n\n"
                        f"<b>Requested:</b> {_fmt_ftc(amount)}\n"
                        f"<b>Available:</b> {_fmt_ftc(data['ftc_balance'])}\n\n"
                        "Please enter a lower amount.",
                        kb_back_cancel(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                # Store amount and move to confirmation
                data["amount"] = amount
                data["zar_equivalent"] = amount  # 1:1 conversion
                set_step(fsm, msg.chat_id, CMD, S_CONFIRM_OFFRAMP, data)

                confirmation_msg = (
                    "💱 <b>Off-Ramp Confirmation</b>\n\n"
                    f"<b>Amount to Off-Ramp:</b> {_fmt_ftc(amount)}\n"
                    f"<b>ZAR Equivalent:</b> R{amount:,.2f}\n"
                    f"<b>Remaining Balance:</b> {_fmt_ftc(data['ftc_balance'] - amount)}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "<b>⚠️ MVP Notice:</b>\n"
                    f"<i>In a production environment, R{amount:,.2f} would be transferred to your "
                    "bank account via an exchange partner. For this MVP demonstration, we'll burn "
                    "the FTC tokens to simulate the off-ramp process.</i>\n\n"
                    "Confirm to proceed?"
                )

                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    confirmation_msg,
                    kb_confirm(),
                    data=data,
                    parse_mode="HTML",
                )
                return

            except ValueError:
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ <b>Invalid Amount</b>\n\n"
                    "Please enter a valid number.\n\n"
                    "<i>Example: 150</i>",
                    kb_back_cancel(),
                    data=data,
                    parse_mode="HTML",
                )
                return

        # Fallback
        if step in [S_SELECT_AMOUNT, S_CONFIRM_OFFRAMP]:
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "⚠️ <i>Please use the buttons to navigate.</i>",
                data=data,
                parse_mode="HTML",
            )
            return

        clear_flow(fsm, msg.chat_id)
        reply(
            msg,
            "❌ <b>Session Lost</b>\n\n"
            "Your session has expired. Please use /offramp to start again.",
            parse_mode="HTML",
        )
