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

from backend.apps.users.models import TelegramUser
from backend.apps.users.crypto import decrypt_secret
from backend.apps.loans.models import Loan, Repayment, LoanEvent
from backend.apps.tokens.services.ftc_token import FTCTokenService
from backend.apps.tokens.services.loan_system import LoanSystemService
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


def _fmt_money(amount: int) -> str:
    """Format integer ZAR amount as currency string."""
    return f"R{amount:,.2f}"


def _fmt_ftc(amount: float) -> str:
    """Format FTC amount."""
    return f"{amount:,.2f} FTC"


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
        total_due = loan.amount + loan.interest_portion
        remaining = total_due - loan.repaid_amount
        label = f"💰 R{loan.amount:,} • Due: {_fmt_date(loan.due_date)} • Remaining: R{remaining:,}"
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
                
                # Get active loans (disbursed state)
                active_loans = list(Loan.objects.filter(
                    user=user,
                    state="disbursed"
                ).order_by("-created_at"))
                
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
                    active_loans = list(Loan.objects.filter(
                        user=user,
                        state="disbursed"
                    ).order_by("-created_at"))
                    
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
                    
                    # Calculate total due and remaining using on-chain values
                    onchain_total = Decimal(str(loan.amount)) + onchain_interest
                    remaining_decimal = onchain_total - Decimal(str(loan.repaid_amount))
                    
                    # Database values for display
                    total_due = loan.amount + loan.interest_portion
                    remaining = total_due - loan.repaid_amount
                    
                    # Use on-chain calculation for FTC amount to avoid rounding issues
                    ftc_amount = float(remaining_decimal)
                    
                    # Log any discrepancy between database and on-chain calculations
                    if abs(float(onchain_interest) - loan.interest_portion) > 0.01:
                        logger.warning(
                            f"Interest mismatch for loan {loan.id}: "
                            f"DB={loan.interest_portion}, OnChain={onchain_interest}"
                        )
                    
                    # Check if repayment is on time
                    is_on_time = timezone.now() <= loan.due_date if loan.due_date else True
                    
                    # Store in data
                    data["loan_id"] = loan_id
                    data["loan_amount"] = loan.amount
                    data["interest"] = loan.interest_portion
                    data["onchain_interest"] = float(onchain_interest)
                    data["total_due"] = total_due
                    data["remaining"] = remaining
                    data["ftc_amount"] = ftc_amount
                    data["onchain_loan_id"] = loan.onchain_loan_id
                    data["is_on_time"] = is_on_time
                    data["due_date"] = _fmt_date(loan.due_date)
                    
                    set_step(fsm, msg.chat_id, CMD, S_CONFIRM_AMOUNT, data)
                    
                    # Show confirmation
                    # Calculate interest amount correctly with decimals
                    interest_amount = float(onchain_interest)
                    total_amount = loan.amount + interest_amount
                    
                    confirmation_text = (
                        f"💰 <b>Repayment Confirmation</b>\n\n"
                        f"<b>Loan ID:</b> <code>{loan_id[:8]}...</code>\n"
                        f"<b>On-Chain ID:</b> {loan.onchain_loan_id}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<b>Loan Details:</b>\n"
                        f"• Principal: {_fmt_money(loan.amount)}\n"
                        f"• Interest (on-chain): R{interest_amount:.2f}\n"
                        f"• Total Due: R{total_amount:.2f}\n"
                        f"• Already Paid: {_fmt_money(loan.repaid_amount)}\n\n"
                        f"<b>Remaining Balance:</b> R{float(remaining_decimal):.2f}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<b>Payment Amount:</b> {_fmt_ftc(ftc_amount)}\n"
                        f"<b>Due Date:</b> {data['due_date']}\n"
                        f"<b>Status:</b> {'✅ On Time' if is_on_time else '⚠️ Late'}\n\n"
                    )
                    
                    if is_on_time:
                        confirmation_text += "<i>✨ Paying on time will boost your credit score!</i>\n\n"
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
                    
                    if not hasattr(user, 'wallet') or not user.wallet:
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
                    
                    # Initialize services
                    ftc_service = FTCTokenService()
                    loan_service = LoanSystemService()
                    
                    ftc_amount = data["ftc_amount"]
                    onchain_loan_id = data["onchain_loan_id"]
                    is_on_time = data["is_on_time"]
                    
                    # Check FTC balance
                    user_ftc_balance = ftc_service.get_balance(wallet_address)
                    if user_ftc_balance < Decimal(str(ftc_amount)):
                        mark_prev_keyboard(data, msg)
                        reply(
                            msg,
                            f"❌ <b>Insufficient Balance</b>\n\n"
                            f"Required: {_fmt_ftc(ftc_amount)}\n"
                            f"Your balance: {_fmt_ftc(float(user_ftc_balance))}\n\n"
                            f"Please acquire more FTC tokens first.",
                            data=data,
                            parse_mode="HTML",
                        )
                        clear_flow(fsm, msg.chat_id)
                        return
                    
                    # Log repayment details for debugging
                    logger.info(
                        f"[Repay] Processing repayment for loan {loan.id} (on-chain ID: {onchain_loan_id})\n"
                        f"  Principal: {loan.amount}, APR: {loan.apr_bps}bps, Term: {loan.term_days}d\n"
                        f"  FTC Amount to send: {ftc_amount}"
                    )
                    
                    # STEP 1: Approve LoanSystem to spend FTC
                    logger.info(f"[Repay] User {user.telegram_id} approving {ftc_amount} FTC for loan {loan.id}")
                    approve_result = ftc_service.approve(
                        owner_address=wallet_address,
                        spender_address=settings.LOANSYSTEM_ADDRESS,
                        amount=ftc_amount,
                        private_key=user_private_key,
                    )
                    logger.info(f"[Repay] Approved: {approve_result['tx_hash']}")
                    
                    # STEP 2: Mark repaid on-chain
                    # Since they might not have enough XRP, we need to send some for gas
                    user_xrp_balance = ftc_service.web3.eth.get_balance(wallet_address)
                    if user_xrp_balance < ftc_service.web3.to_wei(0.05, 'ether'):
                        logger.info(f"[Repay] User likely does not have enough XRP to pay for gas, skipping repayment")
                        # Reply that the user can use /buyftc to be credited with XRP for gas
                        mark_prev_keyboard(data, msg)
                        reply(
                            msg,
                            "❌ <b>Insufficient XRP Balance</b>\n\n"
                            "You do not have enough XRP to pay for gas. Please use /buyftc to be credited with XRP for gas.",
                            data=data,
                            parse_mode="HTML",
                        )
                        return
                    
                    logger.info(f"[Repay] Marking loan {onchain_loan_id} as repaid on-chain with {ftc_amount} FTC")
                    repay_result = loan_service.mark_repaid_ftct(
                        loan_id=onchain_loan_id,
                        on_time=is_on_time,
                        amount=ftc_amount,
                        borrower_address=wallet_address,
                        borrower_private_key=user_private_key,
                    )
                    logger.info(f"[Repay] Repaid successfully: {repay_result['tx_hash']}")
                    
                    # STEP 3: Update database
                    # Use the actual amount we paid (from on-chain calculation)
                    loan.repaid_amount += int(ftc_amount)
                    
                    # Update interest_portion to match on-chain value if different
                    if abs(data["onchain_interest"] - loan.interest_portion) > 0.01:
                        logger.info(
                            f"[Repay] Updating interest_portion from {loan.interest_portion} to {data['onchain_interest']}"
                        )
                        loan.interest_portion = int(data["onchain_interest"])
                    
                    # Check if fully repaid (using on-chain calculation)
                    total_due_onchain = loan.amount + loan.interest_portion
                    if loan.repaid_amount >= total_due_onchain:
                        loan.state = "repaid"
                        logger.info(f"[Repay] Loan {loan.id} marked as fully repaid")
                    
                    loan.save()
                    
                    # Create repayment record
                    repayment = Repayment.objects.create(
                        loan=loan,
                        amount=int(ftc_amount),
                        method="telegram",
                        tx_hash=repay_result['tx_hash'],
                        meta={
                            "on_time": is_on_time,
                            "ftc_amount": ftc_amount,
                            "approve_tx": approve_result['tx_hash'],
                            "onchain_interest": data["onchain_interest"],
                        }
                    )
                    
                    # Create loan event
                    LoanEvent.objects.create(
                        loan=loan,
                        name="repaid" if loan.state == "repaid" else "partial_repayment",
                        details={
                            "amount": int(ftc_amount),
                            "ftc_amount": ftc_amount,
                            "tx_hash": repay_result['tx_hash'],
                            "on_time": is_on_time,
                            "onchain_interest": data["onchain_interest"],
                        }
                    )
                    
                    # Calculate remaining balance
                    remaining_balance = total_due_onchain - loan.repaid_amount
                    
                    # Success message
                    success_text = (
                        f"✅ <b>Repayment Successful!</b>\n\n"
                        f"<b>Loan ID:</b> <code>{data['loan_id'][:8]}...</code>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<b>Payment Details:</b>\n"
                        f"• Amount Paid: R{ftc_amount:.2f}\n"
                        f"• FTC Used: {_fmt_ftc(ftc_amount)}\n"
                        f"• New Balance: R{remaining_balance:.2f}\n\n"
                        f"<b>Transactions:</b>\n"
                        f"1️⃣ Approve: <code>{approve_result['tx_hash'][:16]}...</code>\n"
                        f"2️⃣ Repayment: <code>{repay_result['tx_hash'][:16]}...</code>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    )
                    
                    if loan.state == "repaid":
                        success_text += (
                            f"🎉 <b>Loan Fully Repaid!</b>\n\n"
                            f"Congratulations! You've successfully paid off this loan.\n"
                        )
                        if is_on_time:
                            success_text += f"\n✨ Your credit score has been boosted for on-time payment!"
                    else:
                        success_text += (
                            f"📊 <b>Remaining Balance:</b> R{remaining_balance:.2f}\n\n"
                            f"Use /repay again to make another payment."
                        )
                    
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        success_text,
                        data=data,
                        parse_mode="HTML",
                    )
                    
                    # Trigger credit score update after successful repayment
                    from backend.apps.scoring.tasks import start_scoring_pipeline
                    try:
                        start_scoring_pipeline.delay(user.id)
                        logger.info(f"[Repay] Triggered credit scoring update for user {user.id}")
                    except Exception as scoring_error:
                        logger.error(f"[Repay] Failed to trigger scoring update: {scoring_error}")
                        # Don't fail the repayment if scoring fails
                    
                    clear_flow(fsm, msg.chat_id)
                    return
                    
                except Exception as e:
                    logger.error(f"[Repay] Error processing repayment: {e}", exc_info=True)
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

