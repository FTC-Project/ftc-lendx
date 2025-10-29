from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from celery import shared_task
from django.utils import timezone
from django.db import transaction

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
from backend.apps.scoring.models import AffordabilitySnapshot
from backend.apps.loans.models import Loan, LoanOffer, RepaymentSchedule
from backend.apps.telegram_bot.tasks import process_loan_onchain

logger = logging.getLogger(__name__)

# -------- Flow config --------
CMD = "apply"

S_AMOUNT = "awaiting_amount"
S_TERM = "awaiting_term"
S_OFFER = "awaiting_offer"
S_DETAILS = "awaiting_details_view"
S_CONFIRM = "awaiting_confirm"

PREV: Dict[str, Optional[str]] = {
    S_TERM: S_AMOUNT,
    S_OFFER: S_TERM,
    S_DETAILS: S_OFFER,
    S_CONFIRM: S_OFFER,
}


def get_offer_keyboard() -> dict:
    rows = [
        [
            {"text": "✅ Accept Terms", "callback_data": "flow:accept"},
            {"text": "❌ Decline", "callback_data": "flow:decline"},
        ],
        [{"text": "📄 View Details", "callback_data": "flow:view_details"}],
    ]
    return kb_back_cancel(rows)


def prompt_for(step: str, data: Optional[Dict[str, Any]]) -> str:
    prompts = {
        S_AMOUNT: (
            f"💰 <b>Loan Application</b>\n\n"
            f"What loan amount would you like to apply for?\n\n"
            f"<b>Your maximum:</b> R{int(data.get('limit', 0)):,}\n\n"
            f"<i>Enter an amount in ZAR (e.g., 500)</i>\n\n"
            f"<i>Note: We denote amounts in ZAR, but you are taking out the loan in FTC.</i>"
        ),
        S_TERM: (
            "📅 <b>Loan Term</b>\n\n"
            "How many days would you like to repay the loan?\n\n"
            "<i>Enter a number between 1 and 365 days (e.g., 30)</i>"
        ),
        S_OFFER: "Please review your loan offer below.",
        S_DETAILS: "Here is the repayment schedule for your loan.",
        S_CONFIRM: "Please confirm your loan application.",
    }
    return prompts[step]


def render_offer_summary(data: dict) -> str:
    amount = data.get('amount', 0)
    term_days = data.get('term_days', 0)
    apr = data.get('apr', 0)
    total_repayable = data.get('total_repayable', 0)
    interest = data.get('interest', 0)
    due_date = data.get('due_date', 'N/A')
    
    return (
        f"📋 <b>Loan Offer Summary</b>\n\n"
        f"<i>Note: We denote amounts in ZAR, but you are taking out the loan in FTC.</i>\n\n"
        f"<b>Loan Details:</b>\n"
        f"• Principal: {amount:.2f} FTC\n"
        f"• Term: {term_days} days\n"
        f"• Interest Rate (APR): {apr:.2f}%\n"
        f"• Interest Amount: {interest:.2f} FTC\n\n"
        f"<b>Total Repayable:</b> {total_repayable:.2f} FTC\n"
        f"<b>Due Date:</b> {due_date}\n"
    )


def render_repayment_schedule(data: dict) -> str:
    schedule = data.get("schedule", [])
    if not schedule:
        return "📅 <b>Repayment Schedule</b>\n\n<i>No repayment schedule available.</i>"

    details = "📅 <b>Repayment Schedule</b>\n\n"
    for idx, item in enumerate(schedule, 1):
        details += (
            f"<b>Payment {idx}:</b>\n"
            f"• Due Date: {item['due_at']}\n"
            f"• Amount: R{item['amount_due']:,}\n\n"
        )
    return details.rstrip()


def calculate_loan_details(amount: int, term_days: int, apr: float) -> dict:
    # Using simple interest for this POC.
    interest = (amount) * (apr / 100) * (term_days / 365)
    total_repayable = int(round(amount + interest))
    due_date = timezone.now().date() + datetime.timedelta(days=term_days)

    # For this POC, we assume a single repayment at the end of the term.
    schedule = [
        {
            "installment_no": 1,
            "due_at": due_date.strftime("%Y-%m-%d"),
            "amount_due": total_repayable,
        }
    ]

    return {
        "total_repayable": total_repayable,
        "due_date": due_date.strftime("%Y-%m-%d"),
        "schedule": schedule,
        "interest": round(interest, 2),
    }


@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="Apply for a loan",
    permission="verified_borrower",
)
class ApplyCommand(BaseCommand):
    name = CMD
    description = "Apply for a loan"
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
            user = TelegramUser.objects.filter(telegram_id=msg.user_id).first()
            if not user or not user.is_registered or user.role != "borrower":
                clear_flow(fsm, msg.chat_id)
                reply(
                    msg,
                    "❌ <b>Access Denied</b>\n\n"
                    "You must be a registered borrower to apply for a loan.\n\n"
                    "Use /register to get started.",
                    parse_mode="HTML",
                )
                return

            affordability = (
                AffordabilitySnapshot.objects.filter(user=user)
                .order_by("-calculated_at")
                .first()
            )
            if not affordability or affordability.limit <= 0:
                clear_flow(fsm, msg.chat_id)
                reply(
                    msg,
                    "❌ <b>Not Eligible</b>\n\n"
                    "We couldn't determine your loan eligibility at this time.\n\n"
                    "You may need to:\n"
                    "• Link a bank account (/linkbank)\n"
                    "• Wait for your credit score to be calculated\n\n"
                    "Use /status to check your eligibility.",
                    parse_mode="HTML",
                )
                return

            # Convert Decimal to float for serialization
            data = {
                "limit": float(affordability.limit),
                "apr": float(affordability.apr),
            }
            start_flow(fsm, msg.chat_id, CMD, data, S_AMOUNT)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_AMOUNT, data), kb_back_cancel(), data=data, parse_mode="HTML")
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
                    "❌ <b>Application Cancelled</b>\n\n"
                    "Your loan application has been cancelled.\n\n"
                    "Use /apply to start a new application.",
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
                        "👋 <b>Exiting Application</b>\n\n"
                        "Loan application cancelled.",
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                set_step(fsm, msg.chat_id, CMD, prev, data)
                mark_prev_keyboard(data, msg)

                kb = kb_back_cancel()
                if prev == S_OFFER:
                    kb = get_offer_keyboard()

                text = prompt_for(prev, data)
                if prev == S_OFFER:
                    text = render_offer_summary(data)

                reply(msg, text, kb, data=data, parse_mode="HTML")
                return

            if step == S_OFFER:
                if cb == "flow:accept":
                    set_step(fsm, msg.chat_id, CMD, S_CONFIRM, data)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        f"{render_offer_summary(data)}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<b>⚠️ Please confirm your application</b>\n\n"
                        f"<i>By confirming, you agree to the loan terms above.</i>",
                        kb_confirm(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                if cb == "flow:decline":
                    user = TelegramUser.objects.get(telegram_id=msg.user_id)
                    Loan.objects.create(
                        user=user,
                        amount=data["amount"],
                        term_days=data["term_days"],
                        apr_bps=int(data["apr"] * 100),
                        state="declined",
                    )
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ <b>Offer Declined</b>\n\n"
                        "You have declined this loan offer.\n\n"
                        "You can start a new application with /apply anytime.",
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                if cb == "flow:view_details":
                    set_step(fsm, msg.chat_id, CMD, S_DETAILS, data)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        render_repayment_schedule(data),
                        kb_back_cancel(
                            [[{"text": "« Back to Offer", "callback_data": "flow:back"}]]
                        ),
                        data=data,
                        parse_mode="HTML",
                    )
                    return

            if cb == "flow:confirm" and step == S_CONFIRM:
                try:
                    user = TelegramUser.objects.get(telegram_id=msg.user_id)
                    # Show processing message
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "✅ <b>Application Submitted!</b>\n\n"
                        "⏳ <b>Processing your loan on the blockchain...</b>\n\n"
                        "<i>We're creating your loan on the blockchain. "
                        "This may take a few moments. You'll be notified when it's ready.</i>",
                        data=data,
                        parse_mode="HTML",
                    )

                    # Create loan and related records in a transaction to prevent signal from firing
                    with transaction.atomic():
                        # Temporarily disconnect signal to prevent automatic on-chain processing
                        from django.db.models.signals import post_save
                        from backend.apps.loans.signals import create_loan_on_chain
                        
                        post_save.disconnect(create_loan_on_chain, sender=Loan)
                        
                        try:
                            loan = Loan.objects.create(
                                user=user,
                                amount=data["amount"],
                                term_days=data["term_days"],
                                apr_bps=int(data["apr"] * 100),
                                state="created",
                                due_date=datetime.datetime.strptime(
                                    data["due_date"], "%Y-%m-%d"
                                ).date(),
                                interest_portion=data["interest"],
                            )

                            LoanOffer.objects.create(
                                loan=loan,
                                monthly_payment=data[
                                    "total_repayable"
                                ],  # Simplified for single payment
                                total_repayable=data["total_repayable"],
                                breakdown={"schedule": data["schedule"]},
                            )

                            for item in data["schedule"]:
                                RepaymentSchedule.objects.create(
                                    loan=loan,
                                    installment_no=item["installment_no"],
                                    due_at=datetime.datetime.strptime(item["due_at"], "%Y-%m-%d"),
                                    amount_due=item["amount_due"],
                                )
                        finally:
                            # Reconnect signal
                            post_save.connect(create_loan_on_chain, sender=Loan)

                    
                    
                    # Process on-chain asynchronously
                    logger.info(f"[Apply] Triggering async on-chain processing for loan {loan.id}")
                    process_loan_onchain.delay(str(loan.id), msg.chat_id)
                    
                except Exception as e:
                    logger.error(f"[Apply] Error creating loan: {e}", exc_info=True)
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "❌ <b>Application Failed</b>\n\n"
                        f"An error occurred while processing your application.\n\n"
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

        text = (msg.text or "").strip()

        if step == S_AMOUNT:
            try:
                amount = int(text)
                if amount <= 0 or amount > int(data["limit"]):
                    raise ValueError()
                data["amount"] = amount
                set_step(fsm, msg.chat_id, CMD, S_TERM, data)
                mark_prev_keyboard(data, msg)
                reply(msg, prompt_for(S_TERM, data), kb_back_cancel(), data=data, parse_mode="HTML")
            except (ValueError, TypeError):
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    f"❌ <b>Invalid Amount</b>\n\n"
                    f"Please enter a number between <b>R1</b> and <b>R{int(data['limit']):,}</b>.",
                    kb_back_cancel(),
                    data=data,
                    parse_mode="HTML",
                )
            return

        if step == S_TERM:
            try:
                term_days = int(text)
                if not (1 <= term_days <= 365):
                    raise ValueError()
                data["term_days"] = term_days

                loan_details = calculate_loan_details(
                    data["amount"], data["term_days"], data["apr"]
                )
                data.update(loan_details)

                set_step(fsm, msg.chat_id, CMD, S_OFFER, data)
                mark_prev_keyboard(data, msg)
                reply(msg, render_offer_summary(data), get_offer_keyboard(), data=data, parse_mode="HTML")
            except (ValueError, TypeError):
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ <b>Invalid Term</b>\n\n"
                    "Please enter a number of days between <b>1</b> and <b>365</b>.\n\n"
                    "<i>Example: 30 for a 30-day loan</i>",
                    kb_back_cancel(),
                    data=data,
                    parse_mode="HTML",
                )
            return

        if step == S_DETAILS:
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                render_repayment_schedule(data),
                kb_back_cancel(
                    [[{"text": "« Back to Offer", "callback_data": "flow:back"}]]
                ),
                data=data,
                parse_mode="HTML",
            )
            return

        if step in [S_OFFER, S_CONFIRM]:
            kb = get_offer_keyboard() if step == S_OFFER else kb_confirm()
            summary = render_offer_summary(data)
            text = summary
            if step == S_CONFIRM:
                text = (
                    f"{summary}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"<b>⚠️ Please confirm your application</b>\n\n"
                    f"<i>By confirming, you agree to the loan terms above.</i>"
                )
            mark_prev_keyboard(data, msg)
            reply(msg, text, kb, data=data, parse_mode="HTML")
            return

        clear_flow(fsm, msg.chat_id)
        reply(
            msg, 
            "❌ <b>Session Lost</b>\n\n"
            "Your session has expired. Please use /apply to start again.",
            parse_mode="HTML",
        )
