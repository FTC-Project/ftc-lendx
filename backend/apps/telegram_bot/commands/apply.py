from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

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
from backend.apps.scoring.models import AffordabilitySnapshot
from backend.apps.loans.models import Loan, LoanOffer, RepaymentSchedule

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
        [{"text": "📄 View Details", "callback_data": "flow:view_details"}]
    ]
    return kb_back_cancel(rows)

def prompt_for(step: str, data: Optional[Dict[str, Any]]) -> str:
    prompts = {
        S_AMOUNT: f"What loan amount (in ZAR) would you like to apply for?\n\nYour maximum loan amount is ZAR {int(data.get('limit', 0))}.",
        S_TERM: "What loan term (in days) would you like? (e.g., 30, 60, 90)",
        S_OFFER: "Please review your loan offer below.",
        S_DETAILS: "Here is the repayment schedule for your loan.",
        S_CONFIRM: "Please confirm your loan application.",
    }
    return prompts[step]

def render_offer_summary(data: dict) -> str:
    return (
        "Loan Offer Summary:\n"
        f"• Amount: ZAR {data.get('amount')}\n"
        f"• Term: {data.get('term_days')} days\n"
        f"• Interest Rate (APR): {data.get('apr'):.2f}%\n"
        f"• Total Repayable: ZAR {data.get('total_repayable')}\n"
        f"• Due Date: {data.get('due_date')}\n"
    )

def render_repayment_schedule(data: dict) -> str:
    schedule = data.get('schedule', [])
    if not schedule:
        return "No repayment schedule available."
    
    details = "Repayment Schedule:\n"
    for item in schedule:
        details += f"• Due: {item['due_at']}, Amount: ZAR {item['amount_due']}\n"
    return details

def calculate_loan_details(amount: int, term_days: int, apr: float) -> dict:
    # Using simple interest for this POC.
    interest = (amount) * (apr / 100) * (term_days / 365)
    total_repayable = int(round(amount + interest))
    due_date = timezone.now().date() + datetime.timedelta(days=term_days)
    
    # For this POC, we assume a single repayment at the end of the term.
    schedule = [{
        "installment_no": 1,
        "due_at": due_date.strftime('%Y-%m-%d'),
        "amount_due": total_repayable,
    }]

    return {
        "total_repayable": total_repayable,
        "due_date": due_date.strftime('%Y-%m-%d'),
        "schedule": schedule,
        "interest": int(round(interest)),
    }

@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="Apply for a loan",
    permission="borrower",
)
class ApplyCommand(BaseCommand):
    name = CMD
    description = "Apply for a loan"
    permission = "borrower"

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
            if not user or not user.is_registered or user.role != 'borrower':
                clear_flow(fsm, msg.chat_id)
                reply(msg, "You must be a registered borrower to apply for a loan. Use /register to get started.")
                return

            affordability = AffordabilitySnapshot.objects.filter(user=user).order_by('-calculated_at').first()
            if not affordability or affordability.limit <= 0:
                clear_flow(fsm, msg.chat_id)
                reply(msg, "We couldn't determine your loan eligibility at this time. You may need to link a bank account or wait for your score to be calculated.")
                return

            # Convert Decimal to float for serialization

            data = {
                "limit": float(affordability.limit),
                "apr": float(affordability.apr),
            }
            start_flow(fsm, msg.chat_id, CMD, data, S_AMOUNT)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_AMOUNT, data), kb_back_cancel(), data=data)
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
                reply(msg, "Loan application cancelled.", data=data)
                return

            if cb == "flow:back":
                prev = prev_step_of(PREV, step)
                if prev is None:
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(msg, "Loan application cancelled.", data=data)
                    return
                
                set_step(fsm, msg.chat_id, CMD, prev, data)
                mark_prev_keyboard(data, msg)
                
                kb = kb_back_cancel()
                if prev == S_OFFER:
                    kb = get_offer_keyboard()

                text = prompt_for(prev, data)
                if prev == S_OFFER:
                    text = render_offer_summary(data)

                reply(msg, text, kb, data=data)
                return

            if step == S_OFFER:
                if cb == "flow:accept":
                    set_step(fsm, msg.chat_id, CMD, S_CONFIRM, data)
                    mark_prev_keyboard(data, msg)
                    reply(msg, f"{render_offer_summary(data)}\n\nPlease confirm your application.", kb_confirm(), data=data)
                    return
                
                if cb == "flow:decline":
                    user = TelegramUser.objects.get(telegram_id=msg.user_id)
                    Loan.objects.create(
                        user=user,
                        amount=data['amount'],
                        term_days=data['term_days'],
                        apr_bps=int(data['apr'] * 100),
                        state='declined',
                    )
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(msg, "Loan offer declined. You can start a new application with /apply.", data=data)
                    return

                if cb == "flow:view_details":
                    set_step(fsm, msg.chat_id, CMD, S_DETAILS, data)
                    mark_prev_keyboard(data, msg)
                    reply(msg, render_repayment_schedule(data), kb_back_cancel([[{"text": "Back to Offer", "callback_data": "flow:back"}]]), data=data)
                    return

            if cb == "flow:confirm" and step == S_CONFIRM:
                user = TelegramUser.objects.get(telegram_id=msg.user_id)
                
                loan = Loan.objects.create(
                    user=user,
                    amount=data['amount'],
                    term_days=data['term_days'],
                    apr_bps=int(data['apr'] * 100),
                    state='created',
                    due_date=datetime.datetime.strptime(data['due_date'], '%Y-%m-%d').date(),
                    interest_portion=data['interest']
                )
                
                LoanOffer.objects.create(
                    loan=loan,
                    monthly_payment=data['total_repayable'], # Simplified for single payment
                    total_repayable=data['total_repayable'],
                    breakdown={'schedule': data['schedule']}
                )

                for item in data['schedule']:
                    RepaymentSchedule.objects.create(
                        loan=loan,
                        installment_no=item['installment_no'],
                        due_at=datetime.datetime.strptime(item['due_at'], '%Y-%m-%d'),
                        amount_due=item['amount_due']
                    )

                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(msg, "✅ Your loan application has been submitted! We will notify you once it is funded.", data=data)
                return

            mark_prev_keyboard(data, msg)
            reply(msg, "Unsupported action. Please use the buttons.", data=data)
            return

        text = (msg.text or "").strip()

        if step == S_AMOUNT:
            try:
                amount = int(text)
                if amount <= 0 or amount > int(data['limit']):
                    raise ValueError()
                data['amount'] = amount
                set_step(fsm, msg.chat_id, CMD, S_TERM, data)
                mark_prev_keyboard(data, msg)
                reply(msg, prompt_for(S_TERM, data), kb_back_cancel(), data=data)
            except (ValueError, TypeError):
                mark_prev_keyboard(data, msg)
                reply(msg, f"Invalid amount. Please enter a number between 1 and {int(data['limit'])}.", kb_back_cancel(), data=data)
            return

        if step == S_TERM:
            try:
                term_days = int(text)
                if not (1 <= term_days <= 365):
                     raise ValueError()
                data['term_days'] = term_days
                
                loan_details = calculate_loan_details(data['amount'], data['term_days'], data['apr'])
                data.update(loan_details)

                set_step(fsm, msg.chat_id, CMD, S_OFFER, data)
                mark_prev_keyboard(data, msg)
                reply(msg, render_offer_summary(data), get_offer_keyboard(), data=data)
            except (ValueError, TypeError):
                mark_prev_keyboard(data, msg)
                reply(msg, "Invalid term. Please enter a number of days (e.g., 30).", kb_back_cancel(), data=data)
            return
        
        if step == S_DETAILS:
            mark_prev_keyboard(data, msg)
            reply(msg, render_repayment_schedule(data), kb_back_cancel([[{"text": "Back to Offer", "callback_data": "flow:back"}]]), data=data)
            return

        if step in [S_OFFER, S_CONFIRM]:
            kb = get_offer_keyboard() if step == S_OFFER else kb_confirm()
            summary = render_offer_summary(data)
            text = summary
            if step == S_CONFIRM:
                text = f"{summary}\n\nPlease confirm your application."
            mark_prev_keyboard(data, msg)
            reply(msg, text, kb, data=data)
            return

        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please /apply again.")