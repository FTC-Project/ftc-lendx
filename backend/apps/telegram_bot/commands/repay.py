from __future__ import annotations

from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime

from celery import shared_task
from django.utils import timezone

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.flow import (
    start_flow,
    set_step,
    clear_flow,
    prev_step_of,
    mark_prev_keyboard,
    reply,
)
from backend.apps.telegram_bot.keyboards import kb_back_cancel, kb_confirm

from backend.apps.tokens.services.credittrust_sync import CreditTrustSyncService
from backend.apps.users.models import TelegramUser
from backend.apps.users.crypto import decrypt_secret
from backend.apps.loans.models import Loan, Repayment, LoanEvent, RepaymentSchedule
from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.tokens.services.ftc_token import FTCTokenService
from django.conf import settings

import logging

logger = logging.getLogger(__name__)

# -------- Flow config --------
CMD = "repay"

S_SELECT_LOAN = "select_loan"
S_CONFIRM_AMOUNT = "confirm_amount"
S_PROCESSING = "processing"

PREV: Dict[str, Optional[str]] = {
    S_SELECT_LOAN: None,
    S_CONFIRM_AMOUNT: S_SELECT_LOAN,
    S_PROCESSING: S_CONFIRM_AMOUNT,
}


def _fmt_money(amount: float) -> str:
    """Format float ZAR amount as currency string."""
    return f"R{amount:,.2f}"


def _fmt_ftc(amount: float) -> str:
    """Format FTC amount."""
    return f"{amount:,.8f} FTC"  # Increased precision for display


def _fmt_date(d) -> str:
    """Format date/datetime objects."""
    if not d:
        return "N/A"
    if isinstance(d, (datetime,)):
        return d.strftime("%Y-%m-%d")
    return str(d)


def kb_loan_selector(loans: list) -> dict:
    """Build keyboard for selecting a loan."""
    rows = []
    for loan in loans:
        # Get loan schedule object for the due date of the first (and only) installment
        schedule = RepaymentSchedule.objects.filter(loan=loan, installment_no=1).first()
        due_date = _fmt_date(schedule.due_at) if schedule else _fmt_date(loan.due_date)
        # Use float() for all amount calculations
        total_due = float(loan.amount) + float(loan.interest_portion)
        remaining = total_due - float(loan.repaid_amount)
        label = f"💰 R{loan.amount:,} • Due: {due_date} • Remaining: R{remaining:,.2f}"
        rows.append([{"text": label, "callback_data": f"repay:select:{loan.id}"}])

    return kb_back_cancel(rows)


@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="Repay your active loans",
    permission="verified_borrower",
)
class RepayCommand(BaseCommand):
    """Allows users to repay their active loans."""

    name = CMD
    description = "Repay your active loans"
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

                # Check user's XRP balance (needed for gas fees)
                wallet_address = user.wallet.address
                ftc_service = FTCTokenService()
                xrp_balance_wei = ftc_service.web3.eth.get_balance(wallet_address)
                xrp_balance = float(ftc_service.web3.from_wei(xrp_balance_wei, "ether"))

                # If user has low XRP, tell them to use /buyftc to get some
                if xrp_balance < 1.0:
                    mark_prev_keyboard({}, msg)
                    reply(
                        msg,
                        "⛽ <b>Low XRP Balance</b>\n\n"
                        f"Your current XRP balance: {xrp_balance:.4f} XRP\n\n"
                        "⚠️ You need XRP (gas) to complete the repayment transaction.\n\n"
                        "💡 <b>Solution:</b> Use /buyftc to get XRP. "
                        "The buyftc command will automatically send you test XRP if your balance is low.\n\n"
                        "<i>After getting XRP, you can return here to complete your repayment.</i>",
                        parse_mode="HTML",
                    )
                    return

                # Get active loans (disbursed state)
                active_loans = list(
                    Loan.objects.filter(user=user, state="disbursed").order_by(
                        "-created_at"
                    )
                )

                if not active_loans:
                    mark_prev_keyboard({}, msg)
                    reply(
                        msg,
                        "💼 <b>No Active Loans</b>\n\n"
                        "You don't have any active loans to repay.\n\n"
                        "Use /apply to request a new loan or /status to check your loan history.",
                        parse_mode="HTML",
                    )
                    return

                data = {
                    "loan_ids": [str(loan.id) for loan in active_loans],
                }
                start_flow(fsm, msg.chat_id, CMD, data, S_SELECT_LOAN)

                # Show loan selection
                header = (
                    "💳 <b>Loan Repayment</b>\n\n"
                    "Select the loan you'd like to repay:\n"
                )

                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    header,
                    kb_loan_selector(active_loans),
                    data=data,
                    parse_mode="HTML",
                )
                return

            except TelegramUser.DoesNotExist:
                mark_prev_keyboard({}, msg)
                reply(msg, "User not found. Please /start first.")
                return

        # Guard: other command owns this chat
        if state.get("command") != CMD:
            return

        step = state.get("step")
        data = state.get("data", {}) or {}

        # --- Callbacks: cancel/back ---
        cb = getattr(msg, "callback_data", None)
        if cb:
            if cb == "flow:cancel":
                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ Repayment cancelled. Use /repay to start again.",
                    data=data,
                )
                return

            if cb == "flow:back":
                prev = prev_step_of(PREV, step)
                if prev is None:
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(msg, "👋 Exiting repayment flow.", data=data)
                    return

                # Go back to previous step
                set_step(fsm, msg.chat_id, CMD, prev, data)

                if prev == S_SELECT_LOAN:
                    user = TelegramUser.objects.get(telegram_id=msg.user_id)
                    active_loans = list(
                        Loan.objects.filter(user=user, state="disbursed").order_by(
                            "-created_at"
                        )
                    )

                    header = (
                        "💳 <b>Loan Repayment</b>\n\n"
                        "Select the loan you'd like to repay:\n"
                    )

                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        header,
                        kb_loan_selector(active_loans),
                        data=data,
                        parse_mode="HTML",
                    )
                return

            # Loan selection
            if step == S_SELECT_LOAN and cb.startswith("repay:select:"):
                loan_id = cb.split("repay:select:")[1]

                try:
                    loan = Loan.objects.get(id=loan_id, state="disbursed")
                    user = TelegramUser.objects.get(telegram_id=msg.user_id)

                    # Check if loan has onchain_loan_id
                    if not loan.onchain_loan_id:
                        mark_prev_keyboard(data, msg)
                        reply(
                            msg,
                            "❌ <b>Error</b>\n\n"
                            "This loan doesn't have an on-chain ID. "
                            "Please contact support.",
                            data=data,
                            parse_mode="HTML",
                        )
                        return

                    # Calculate interest using on-chain formula (to match contract exactly)
                    loan_service = LoanSystemService()
                    onchain_interest = loan_service.calculate_interest(
                        principal=float(loan.amount),
                        apr_bps=loan.apr_bps,
                        term_days=loan.term_days,
                    )
                    total_due = float(loan.amount) + float(onchain_interest)
                    remaining = total_due - float(loan.repaid_amount)

                    # Again get the schedule object for the due date of the first (and only) installment
                    schedule = RepaymentSchedule.objects.filter(
                        loan=loan, installment_no=1
                    ).first()
                    is_on_time = timezone.now() <= schedule.due_at if schedule else True
                    due_date = (
                        _fmt_date(schedule.due_at)
                        if schedule
                        else _fmt_date(loan.due_date)
                    )

                    # Store in data - all amounts are now consistently float/str
                    data["loan_id"] = str(loan_id)
                    data["loan_amount"] = loan.amount
                    data["interest"] = loan.interest_portion
                    data["onchain_interest"] = float(onchain_interest)
                    data["total_due"] = total_due
                    data["remaining"] = remaining
                    data["ftc_amount"] = total_due
                    data["onchain_loan_id"] = loan.onchain_loan_id
                    data["is_on_time"] = is_on_time
                    data["due_date"] = due_date

                    set_step(fsm, msg.chat_id, CMD, S_CONFIRM_AMOUNT, data)

                    # Show confirmation

                    confirmation_text = (
                        f"💰 <b>Repayment Confirmation</b>\n\n"
                        f"<b>Loan ID:</b> <code>{loan_id[:8]}...</code>\n"
                        f"<b>On-Chain ID:</b> {loan.onchain_loan_id}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<b>Loan Details:</b>\n"
                        f"• Principal: {_fmt_money(data['loan_amount'])}\n"
                        f"• Interest (on-chain): {_fmt_money(data['onchain_interest'])}\n"
                        f"• Total Due: {_fmt_money(data['total_due'])}\n"
                        f"• Already Paid: {_fmt_money(loan.repaid_amount)}\n\n"
                        f"<b>Remaining Balance:</b> {_fmt_money(data['remaining'])}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<b>Payment Amount (FTC):</b> {_fmt_ftc(data['ftc_amount'])}\n"
                        f"<b>Due Date:</b> {due_date}\n"
                        f"<b>Status:</b> {'✅ On Time' if is_on_time else '⚠️ Late'}\n\n"
                    )

                    if is_on_time:
                        confirmation_text += (
                            "<i>✨ Paying on time will boost your credit score!</i>\n\n"
                        )
                    else:
                        confirmation_text += "<i>⚠️ This payment is late. Your credit score may be affected.</i>\n\n"

                    confirmation_text += "Confirm to proceed with repayment."

                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        confirmation_text,
                        kb_confirm(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                except Loan.DoesNotExist:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ Loan not found or already repaid.",
                        data=data,
                    )
                    return

            # Confirm repayment
            if step == S_CONFIRM_AMOUNT and cb == "flow:confirm":
                try:
                    user = TelegramUser.objects.get(telegram_id=msg.user_id)
                    loan = Loan.objects.get(id=data["loan_id"])

                    # Ensure ftc_amount is passed as float
                    if not hasattr(user, "wallet") or not user.wallet:
                        mark_prev_keyboard(data, msg)
                        reply(
                            msg,
                            "❌ <b>No Wallet Found</b>\n\n"
                            "You don't have a wallet. Please contact support.",
                            data=data,
                            parse_mode="HTML",
                        )
                        return

                    wallet_address = user.wallet.address
                    user_private_key = decrypt_secret(user.wallet.secret_encrypted)

                    set_step(fsm, msg.chat_id, CMD, S_PROCESSING, data)

                    # Show processing message
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        f"⏳ <b>Processing Repayment...</b>\n\n"
                        f"Amount: {_fmt_ftc(data['ftc_amount'])}\n"
                        f"Loan ID: <code>{data['loan_id'][:8]}...</code>\n\n"
                        f"<i>Please wait while we process your payment on-chain...</i>",
                        data=data,
                        parse_mode="HTML",
                    )

                    from backend.apps.telegram_bot.tasks import (
                        process_repayment_onchain,
                    )

                    process_repayment_onchain.delay(
                        loan_id=loan.id,
                        user_id=user.id,
                        chat_id=msg.chat_id,
                        wallet_address=wallet_address,
                        user_private_key=user_private_key,
                        ftc_amount=data["ftc_amount"],  # Passed as float
                        is_on_time=data["is_on_time"],
                    )
                    reply(
                        msg,
                        f"⏳ <b>Repayment In Progress</b>\n\nYour repayment is being processed on-chain. You'll see a confirmation when complete.",
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                except Exception as e:
                    logger.error(
                        f"[Repay] Error processing repayment: {e}", exc_info=True
                    )
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        f"❌ <b>Repayment Failed</b>\n\n"
                        f"An error occurred while processing your payment.\n\n"
                        f"<i>Error: {str(e)}</i>\n\n"
                        f"Please try again or contact support.",
                        data=data,
                        parse_mode="HTML",
                    )
                    clear_flow(fsm, msg.chat_id)
                    return

        # Text input (ignore, user should use buttons)
        text = (msg.text or "").strip()

        if step in (S_SELECT_LOAN, S_CONFIRM_AMOUNT):
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "Please use the buttons to navigate.",
                data=data,
            )
            return

        # Fallback
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please use /repay to start again.")
