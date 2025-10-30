# score.py
from typing import Dict, Any, Optional

from celery import shared_task
import requests

from backend.apps.loans.models import Loan
from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.commands.register import register
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.flow import reply
from backend.apps.telegram_bot.keyboards import kb_back_cancel
from backend.apps.users.models import TelegramUser
from typing import Dict, Any, Optional
from backend.apps.scoring.models import AffordabilitySnapshot
from backend.apps.tokens.models import CreditTrustBalance
from backend.apps.tokens.services.tier_calculation import TokenTierCalculator
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.flow import start_flow, set_step, clear_flow, mark_prev_keyboard, prev_step_of

# -------- Flow config --------
CMD = "score"
S_MENU = "score_menu"
S_DETAILS = "score_details"
S_TIPS = "score_tips"

PREV = {
    S_MENU: None,
    S_DETAILS: S_MENU,
    S_TIPS: S_MENU,
}

def kb_score_menu() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "📊 View Score & Tier", "callback_data": "score:view_score"}],
            [{"text": "📈 How to Increase Score", "callback_data": "score:view_tips"}],
            [
                {"text": "🧾 Detailed Breakdown", "callback_data": "score:view_details"},
            ],
            [
                {"text": "⬅️ Back", "callback_data": "flow:cancel"},
            ],
        ]
    }

def render_score_snapshot(snap: AffordabilitySnapshot) -> str:
    # Calculate how much of their limit they have used, basically fetch loans that are disbursed and sum the amounts
    loans = Loan.objects.filter(user=snap.user, state="disbursed")
    used_limit = sum(loan.amount for loan in loans)
    remaining_limit = snap.limit - used_limit if used_limit < snap.limit else 0
    return (
        f"<b>📊 Your Unified Score</b>\n\n"
        f"<b>Score Tier:</b> {snap.score_tier}\n"
        f"<b>Credit Limit:</b> R{snap.limit:,.2f}\n"
        f"<b>Loan Used:</b> R{used_limit:,.2f}\n"
        f"<b>Loan Available:</b> R{remaining_limit:,.2f}\n"
        f"<b>Unified Score:</b> {snap.combined_score}/100\n"
        f"<b>Credit Score:</b> {snap.credit_score}/100\n"
        f"<b>Token Score:</b> {snap.token_score}/100\n"
        f"<b>APR:</b> {snap.apr:.2f}%\n\n"
        f"<i>Better scores unlock higher limits and lower APR.</i>"
    )

def render_score_details(snap: AffordabilitySnapshot) -> str:
    f = snap.credit_factors
    strengths = f.get("strengths", [])
    weaknesses = f.get("weaknesses", [])
    details = ""
    if strengths:
        details += "✅ <b>Strengths:</b>\n" + "\n".join(f"• {s}" for s in strengths) + "\n"
    if weaknesses:
        details += "⚠️ <b>Weaknesses:</b>\n" + "\n".join(f"• {w}" for w in weaknesses) + "\n"
    if not details:
        details = "<i>No factor breakdown available.</i>"
    return (
        f"<b>🧾 Score Breakdown</b>\n\n"
        f"{details}"
    )

def render_score_tips() -> str:
    return (
        "<b>Tips to Increase Your Score</b>\n\n"
        "• Repay loans on time and in full\n"
        "• Grow your CTT token balance\n"
        "• Avoid late payments\n"
        "• Maintain an active account\n"
        "• Keep your bank account linked for up-to-date info"
    )

@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="View your Unified Score, Tier, and Score Breakdown",
    permission="verified_borrower",
)
class UnifiedScoreCommand(BaseCommand):
    name = CMD
    description = "Unified /score command"
    permission = "verified_borrower"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(msg.chat_id)

        # Start flow or menu
        if not state:
            data = {}
            start_flow(fsm, msg.chat_id, CMD, data, S_MENU)
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "<b>💎 Score Dashboard</b>\n\nGet your score, tier, and see detailed breakdowns.",
                kb_score_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        if state.get("command") != CMD:
            return
        step = state.get("step")
        data = state.get("data", {}) or {}
        cb = getattr(msg, "callback_data", None)
        if cb:
            if cb == "flow:cancel":
                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "👋 Exiting Score dashboard. Use /score to come back anytime.",
                    data=data,
                )
                return
            if cb == "flow:back":
                prev = prev_step_of(PREV, step)
                if prev is None:
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(msg, "👋 Exiting Score dashboard.", data=data)
                    return
                # Go back to previous step or menu
                set_step(fsm, msg.chat_id, CMD, prev, data)
                mark_prev_keyboard(data, msg)
                if prev == S_MENU:
                    reply(
                        msg,
                        "<b>💎 Score Dashboard</b>\n\nGet your score, tier, and see detailed breakdowns.",
                        kb_score_menu(),
                        data=data,
                        parse_mode="HTML",
                    )
                return
            if step == S_MENU:
                # View Score
                if cb == "score:view_score":
                    user = TelegramUser.objects.filter(telegram_id=msg.user_id).first()
                    snap = (
                        AffordabilitySnapshot.objects.filter(user=user)
                        .order_by("-calculated_at")
                        .first()
                    )
                    if not snap:
                        reply(
                            msg,
                            "<b>No score snapshot available.</b>\n\nTry again after linking your bank and waiting for first score calculation.",
                            kb_score_menu(),
                            data=data,
                            parse_mode="HTML",
                        )
                        return
                    set_step(fsm, msg.chat_id, CMD, S_MENU, data)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        render_score_snapshot(snap),
                        kb_score_menu(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return
                # Score tips
                if cb == "score:view_tips":
                    set_step(fsm, msg.chat_id, CMD, S_TIPS, data)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        render_score_tips(),
                        kb_back_cancel(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return
                # Details
                if cb == "score:view_details":
                    user = TelegramUser.objects.filter(telegram_id=msg.user_id).first()
                    snap = (
                        AffordabilitySnapshot.objects.filter(user=user)
                        .order_by("-calculated_at")
                        .first()
                    )
                    if not snap:
                        reply(
                            msg,
                            "<b>No score snapshot available.</b>\n\nTry again after linking your bank and waiting for first score calculation.",
                            kb_score_menu(),
                            data=data,
                            parse_mode="HTML",
                        )
                        return
                    set_step(fsm, msg.chat_id, CMD, S_DETAILS, data)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        render_score_details(snap),
                        kb_back_cancel(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return
            # Unknown callback
            mark_prev_keyboard(data, msg)
            reply(msg, "Please choose an option from the menu.", kb_score_menu(), data=data)
            return
        # Fallback: reset flow
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please use /score to start again.")
