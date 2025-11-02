from __future__ import annotations
from typing import Dict, Optional
from datetime import datetime, date

from celery import shared_task

from backend.apps.pool.models import PoolAccount, PoolDeposit, PoolWithdrawal
from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.flow import reply, mark_prev_keyboard, start_flow, clear_flow
from backend.apps.telegram_bot.fsm_store import FSMStore

from backend.apps.users.models import TelegramUser
from backend.apps.tokens.services.ftc_token import FTCTokenService
from backend.apps.tokens.services.credittrust_sync import CreditTrustTokenClient

import logging

logger = logging.getLogger(__name__)


def _fmt_date(d) -> str:
    """Format date/datetime objects for display."""
    if not d:
        return "N/A"
    if isinstance(d, (datetime, date)):
        return d.strftime("%Y-%m-%d %H:%M")
    return str(d)

# -------- Command config --------
CMD = "balance"


@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="Check your FTC and CTT token balances",
    permission="verified",
)
class BalanceCommand(BaseCommand):
    """Displays on-chain FTC and CTT token balances."""

    name = CMD
    description = "Check your FTC and CTT token balances"
    permission = "verified"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(msg.chat_id)
        data = {}

        # Handle callback for history button - check if we have state first
        cb = getattr(msg, "callback_data", None)
        if cb == "balance:history":
            # Make sure this callback belongs to balance command or create new state
            if not state or state.get("command") != CMD:
                start_flow(fsm, msg.chat_id, CMD, {}, "balance")
            
            try:
                user = TelegramUser.objects.get(telegram_id=msg.user_id)
                
                # Get deposit and withdrawal history
                recent_deposits = (
                    PoolDeposit.objects.filter(user=user)
                    .order_by("-created_at")[:10]
                )
                recent_withdrawals = (
                    PoolWithdrawal.objects.filter(user=user)
                    .order_by("-created_at")[:10]
                )

                # Build deposit history section
                deposit_history = ""
                if recent_deposits:
                    deposit_history = (
                        f"📥 <b>Recent Deposits</b> (last {len(recent_deposits)})\n\n"
                    )
                    for deposit in recent_deposits:
                        tx_link = f"<code>{deposit.tx_hash[:12]}...</code>" if deposit.tx_hash else "pending"
                        deposit_history += (
                            f"• <b>{float(deposit.amount):,.2f} FTCT</b>\n"
                            f"  {_fmt_date(deposit.created_at)} | TX: {tx_link}\n\n"
                        )
                else:
                    deposit_history = "📥 <b>Deposits:</b> No deposits yet\n\n"

                # Build withdrawal history section
                withdrawal_history = ""
                if recent_withdrawals:
                    withdrawal_history = (
                        f"📤 <b>Recent Withdrawals</b> (last {len(recent_withdrawals)})\n\n"
                    )
                    for withdrawal in recent_withdrawals:
                        total_amount = float(withdrawal.principal_out + withdrawal.interest_out)
                        tx_link = f"<code>{withdrawal.tx_hash[:12]}...</code>" if withdrawal.tx_hash else "pending"
                        withdrawal_history += (
                            f"• <b>{total_amount:,.2f} FTCT</b>\n"
                            f"  Principal: {float(withdrawal.principal_out):,.2f} | "
                            f"Interest: {float(withdrawal.interest_out):,.2f}\n"
                            f"  {_fmt_date(withdrawal.created_at)} | TX: {tx_link}\n\n"
                        )
                else:
                    withdrawal_history = "📤 <b>Withdrawals:</b> No withdrawals yet\n\n"

                history_text = (
                    f"📜 <b>Deposit & Withdrawal History</b>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{deposit_history}"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{withdrawal_history}"
                )
                
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    history_text,
                    data=data,
                    parse_mode="HTML",
                )
                return
            except TelegramUser.DoesNotExist:
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ User not found",
                    data=data,
                    parse_mode="HTML",
                )
                return
            except Exception as e:
                logger.error(f"Error showing history: {e}")
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ Error loading history",
                    data=data,
                    parse_mode="HTML",
                )
                return

        # Guard: if state exists but belongs to another command, return
        if state and state.get("command") != CMD:
            return

        # If no state, this is a fresh balance command - initialize flow
        if not state:
            start_flow(fsm, msg.chat_id, CMD, data, "balance")
        else:
            data = state.get("data", {}) or {}

        try:
            # Get user and wallet
            user = TelegramUser.objects.get(telegram_id=msg.user_id)

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

            # Fetch on-chain balances
            try:
                # Reply first that we are fetching the balances
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "🔄 <b>Fetching Balances...</b>\n\n"
                    "Please wait while we fetch your token balances from the blockchain.",
                    data=data,
                    parse_mode="HTML",
                )
                # Get FTC balance
                ftc_service = FTCTokenService()
                ftc_balance = ftc_service.get_balance(wallet_address)

                # Get CTT balance
                ctt_client = CreditTrustTokenClient()
                # Weidly CTT is in units of 10^18, so we need to divide by 10^18 to get the actual balance
                ctt_balance = ctt_client.get_balance(wallet_address)
                xrp_balance = ftc_service.web3.from_wei(
                    ftc_service.web3.eth.get_balance(wallet_address), "ether"
                )
                # Format the response message
                if user.role == "lender":
                    # Pool metrics
                    ls = LoanSystemService()
                    total_pool = ls.get_total_pool()
                    total_shares = ls.get_total_shares()
                    user_shares = ls.get_shares_of(wallet_address)
                    user_value = (
                        ls.get_share_value(float(user_shares)) if user_shares > 0 else 0
                    )
                    # PnL: current value - net contributed
                    deposits_sum = sum(
                        float(d.amount) for d in PoolDeposit.objects.filter(user=user)
                    )
                    withdrawals_sum = sum(
                        float(w.principal_out + w.interest_out)
                        for w in PoolWithdrawal.objects.filter(user=user)
                    )
                    net_contrib = deposits_sum - withdrawals_sum
                    pnl = float(user_value) - net_contrib

                    message_text = (
                        f"💰 <b>Your Balances & Pool Position</b>\n\n"
                        f"<b>Wallet:</b> <code>{wallet_address}</code>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"💵 <b>FTC:</b> {ftc_balance:,.2f} FTC\n"
                        f"⛽ <b>XRP (gas):</b> {float(xrp_balance):.4f} XRP\n\n"
                        f"📊 <b>Pool</b>\n"
                        f"• Total Pool: {float(total_pool):,.2f} FTCT\n"
                        f"• Total Shares: {float(total_shares):,.6f}\n"
                        f"• Your Shares: {float(user_shares):,.6f}\n"
                        f"• Your Investment (est.): {float(user_value):,.2f} FTCT\n"
                        f"• Your PnL: {pnl:,.2f} FTCT\n"
                    )
                    
                    # Add history button for lenders
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "📜 View Deposit/Withdrawal History", "callback_data": "balance:history"}
                            ]
                        ]
                    }
                else:
                    message_text = (
                        f"💰 <b>Your Token Balances</b>\n\n"
                        f"<b>Wallet Address:</b>\n"
                        f"<code>{wallet_address}</code>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"💵 <b>FTC Balance:</b> {ftc_balance:,.2f} FTC\n"
                        f"<i>FTCoin - Your main currency</i>\n\n"
                        f"💎 <b>CTT Balance:</b> {ctt_balance:,.0f} CTT\n"
                        f"<i>Credit Trust Tokens - Your creditworthiness score</i>\n\n"
                        f"⛽ XRP (gas): {xrp_balance:.4f} XRP\n"
                        f"<i>Your XRP balance is used for gas fees when interacting with the blockchain.</i>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<i>These are your on-chain token balances fetched directly from the blockchain.</i>"
                    )
                    keyboard = None

                # Update FSM state after successful balance fetch
                start_flow(fsm, msg.chat_id, CMD, data, "balance")
                
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    message_text,
                    reply_markup=keyboard,
                    data=data,
                    parse_mode="HTML",
                )

                logger.info(
                    f"Balance check for user {user.telegram_id}: "
                    f"FTC={ftc_balance}, CTT={ctt_balance}"
                )

            except Exception as e:
                logger.error(
                    f"Error fetching balances for user {user.telegram_id}: {e}"
                )
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ <b>Error Fetching Balances</b>\n\n"
                    "Sorry, we couldn't retrieve your token balances from the blockchain. "
                    "Please try again later.\n\n"
                    f"<i>Error: {str(e)}</i>",
                    data=data,
                    parse_mode="HTML",
                )

        except TelegramUser.DoesNotExist:
            logger.error(f"User not found: {msg.user_id}")
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "❌ <b>User Not Found</b>\n\n" "Please register first using /start",
                data=data,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Unexpected error in balance command: {e}")
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "❌ <b>An Error Occurred</b>\n\n"
                "Something went wrong. Please try again later.",
                data=data,
                parse_mode="HTML",
            )
