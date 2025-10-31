from __future__ import annotations

from typing import Optional, Dict
from decimal import Decimal
from celery import shared_task

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.flow import reply, start_flow, set_step, clear_flow, mark_prev_keyboard
from backend.apps.telegram_bot.fsm_store import FSMStore

from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.users.models import TelegramUser
from backend.apps.users.crypto import decrypt_secret
from backend.apps.pool.models import PoolDeposit, PoolWithdrawal


CMD = "withdraw"

S_SHOW = "show_overview"
S_ENTER_AMOUNT = "enter_amount"
S_CONFIRM = "confirm_withdraw"
S_PROCESS = "processing"

PREV: Dict[str, Optional[str]] = {
    S_SHOW: None,
    S_ENTER_AMOUNT: S_SHOW,
    S_CONFIRM: S_ENTER_AMOUNT,
    S_PROCESS: S_CONFIRM,
}


def _fmt(amount: float) -> str:
    return f"{amount:,.2f}"


def _kb_confirm() -> dict:
    return {"inline_keyboard": [[{"text": "✅ Confirm", "callback_data": "flow:confirm"}], [{"text": "❌ Cancel", "callback_data": "flow:cancel"}]]}


@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="Withdraw FTCT from the pool",
    permission="lender",
)
class WithdrawCommand(BaseCommand):
    name = CMD
    description = "Withdraw FTCT from the pool"
    permission = "lender"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(msg.chat_id)

        # Start flow: show balances and prompt amount
        if not state:
            user = TelegramUser.objects.filter(telegram_id=msg.user_id).first()
            if not user or not user.is_registered or user.role != "lender":
                reply(msg, "⛔ This command is only available to registered lenders.", parse_mode="HTML")
                return

            if not hasattr(user, "wallet") or not user.wallet:
                reply(msg, "❌ No wallet found. Please contact support.")
                return

            ls = LoanSystemService()
            total_pool = float(ls.get_total_pool())
            total_shares = float(ls.get_total_shares())
            user_shares = float(ls.get_shares_of(user.wallet.address))
            user_value = float(ls.get_share_value(user_shares)) if user_shares > 0 else 0.0

            # PnL: current value - net contributed
            deposits = sum(float(d.amount) for d in PoolDeposit.objects.filter(user=user))
            withdrawals = sum(float(w.principal_out + w.interest_out) for w in PoolWithdrawal.objects.filter(user=user))
            net_contrib = deposits - withdrawals
            pnl = user_value - net_contrib

            data = {
                "total_pool": total_pool,
                "total_shares": total_shares,
                "user_shares": user_shares,
                "user_value": user_value,
                "pnl": pnl,
            }

            start_flow(fsm, msg.chat_id, CMD, data, S_ENTER_AMOUNT)

            text = (
                "🏦 <b>Pool Overview</b>\n\n"
                f"<b>Total Pool:</b> {_fmt(total_pool)} FTCT\n"
                f"<b>Your Shares:</b> {user_shares:,.6f}\n"
                f"<b>Your Investment:</b> {_fmt(user_value)} FTCT\n"
                f"<b>Your PnL:</b> {_fmt(pnl)} FTCT\n\n"
                "Enter the amount of FTCT to withdraw:"
            )
            reply(msg, text, parse_mode="HTML")
            return

        # Subsequent steps
        step = state["step"]
        data = state.get("data", {})

        # If callback cancel
        if getattr(msg, "callback_query_id", None) and getattr(msg, "callback_data", None) == "flow:cancel":
            clear_flow(fsm, msg.chat_id)
            reply(msg, "❌ Cancelled")
            return

        # Enter amount (text message)
        if step == S_ENTER_AMOUNT and not getattr(msg, "callback_query_id", None):
            try:
                amt = float((msg.text or "").strip())
                if amt <= 0:
                    raise ValueError
            except Exception:
                reply(msg, "Please enter a valid positive number amount in FTCT.")
                return

            data["withdraw_amount"] = amt
            set_step(fsm, msg.chat_id, CMD, S_CONFIRM, data)
            text = (
                "🔎 <b>Confirm Withdrawal</b>\n\n"
                f"Amount: <b>{_fmt(amt)} FTCT</b>\n"
            )
            reply(msg, text, reply_markup=_kb_confirm(), parse_mode="HTML", data=data)
            return

        # Confirm
        if step == S_CONFIRM and getattr(msg, "callback_data", None) == "flow:confirm":
            set_step(fsm, msg.chat_id, CMD, S_PROCESS, data)
            mark_prev_keyboard(data, msg)
            reply(msg, "⏳ Processing withdrawal...", parse_mode="HTML", data=data)

            process_withdraw_task.delay(message_data)
            return


@shared_task(queue="scoring")
def process_withdraw_task(message_data: dict) -> None:
    msg = TelegramMessage.from_payload(message_data)
    fsm = FSMStore()
    state = fsm.get(msg.chat_id) or {}
    data = state.get("data", {})

    try:
        user = TelegramUser.objects.get(telegram_id=msg.user_id)
        wallet = user.wallet.address
        private_key = decrypt_secret(user.wallet.secret_encrypted)
        amount = float(data.get("withdraw_amount", 0))

        ls = LoanSystemService()
        total_pool = float(ls.get_total_pool())
        total_shares = float(ls.get_total_shares())
        # compute needed shares for desired FTCT amount
        if total_pool <= 0 or total_shares <= 0:
            raise ValueError("Pool is empty")
        shares_needed = Decimal(amount) * Decimal(total_shares) / Decimal(total_pool)

        # Execute withdraw by shares
        result = ls.withdraw_ftct(
            lender_address=wallet,
            share_amount=float(shares_needed),
            lender_private_key=private_key,
        )

        ftct_received = float(result.get("ftct_amount", amount))
        tx_hash = result.get("tx_hash", "")

        # Record withdrawal
        # For simplicity attribute all to principal_out; advanced split would require accounting
        PoolWithdrawal.objects.create(user=user, principal_out=int(ftct_received), interest_out=0, tx_hash=tx_hash)

        # Refresh balances
        user_shares = float(ls.get_shares_of(wallet))
        user_value = float(ls.get_share_value(user_shares)) if user_shares > 0 else 0.0
        deposits = sum(float(d.amount) for d in PoolDeposit.objects.filter(user=user))
        withdrawals = sum(float(w.principal_out + w.interest_out) for w in PoolWithdrawal.objects.filter(user=user))
        pnl = user_value - (deposits - withdrawals)

        text = (
            "✅ <b>Withdrawal Complete</b>\n\n"
            f"Tx: <code>{tx_hash[:16]}...</code>\n"
            f"Received: <b>{_fmt(ftct_received)} FTCT</b>\n\n"
            f"<b>Your Shares:</b> {user_shares:,.6f}\n"
            f"<b>Your Investment:</b> {_fmt(user_value)} FTCT\n"
            f"<b>Your PnL:</b> {_fmt(pnl)} FTCT\n"
        )
        clear_flow(fsm, msg.chat_id)
        reply(msg, text, parse_mode="HTML")
    except Exception as e:
        clear_flow(fsm, msg.chat_id)
        reply(msg, f"❌ Withdrawal failed: {e}")


