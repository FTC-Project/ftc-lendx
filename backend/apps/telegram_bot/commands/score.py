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
from backend.apps.telegram_bot.flow import (
    start_flow,
    set_step,
    clear_flow,
    mark_prev_keyboard,
    prev_step_of,
)

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
                {
                    "text": "🧾 Detailed Breakdown",
                    "callback_data": "score:view_details",
                },
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

    if snap.limit == 0:
        return (
            f"<b>📊 Your Unified Score</b>\n\n"
            f"<b>Score Tier:</b> {snap.score_tier}\n"
            f"⚠️ <b>Credit Limit:</b> R{snap.limit:,.2f}\n"
            f"<b>Unified Score:</b> {snap.combined_score}/100\n"
            f"<b>Credit Score:</b> {snap.credit_score}/100\n"
            f"<b>Token Score:</b> {snap.token_score}/100\n"
            f"<b>APR:</b> {snap.apr:.2f}%\n\n"
            f"<b>📋 Why your limit is R0:</b>\n"
            f"Your spending is currently higher than your income. We cannot offer credit when expenses exceed earnings.\n\n"
            f"<b>💡 How to improve:</b>\n"
            f"• Review and reduce your spending patterns\n"
            f"• Link another bank account if you have additional income sources\n"
            f"• Wait for more transaction history to demonstrate better affordability\n"
            f"• Build your CTT token balance to improve your unified score\n\n"
            f"<i>Better scores and positive affordability unlock higher limits and lower APR.</i>"
        )

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
    """Render credit factors breakdown with human-readable names."""
    f = snap.credit_factors or {}

    # Mapping of factor keys to human-readable names
    factor_names = {
        "months_on_book": "Months on Book",
        "direction_ratio": "Expense to Income Ratio",
        "incoming_volume": "Incoming Volume",
        "outgoing_volume": "Outgoing Volume",
        "incoming_variance": "Incoming Variance",
        "outgoing_variance": "Outgoing Variance",
        "incoming_frequency": "Incoming Frequency",
        "outgoing_frequency": "Outgoing Frequency",
        "affordability_buffer": "Affordability Buffer",
    }

    if not f:
        return "<b>🧾 Score Breakdown</b>\n\n<i>No factor breakdown available.</i>"

    # Group factors logically
    account_stability = []
    transaction_patterns = []
    affordability_metrics = []

    for key, value in f.items():
        if value is None:
            continue

        name = factor_names.get(key, key.replace("_", " ").title())
        formatted_value = (
            f"{float(value):.2f}" if isinstance(value, (int, float)) else str(value)
        )

        if key in ["months_on_book", "direction_ratio"]:
            account_stability.append((name, formatted_value))
        elif key in [
            "incoming_volume",
            "outgoing_volume",
            "incoming_variance",
            "outgoing_variance",
            "incoming_frequency",
            "outgoing_frequency",
        ]:
            transaction_patterns.append((name, formatted_value))
        elif key in ["affordability_buffer"]:
            affordability_metrics.append((name, formatted_value))
        else:
            # Fallback for any unknown factors
            transaction_patterns.append((name, formatted_value))

    details = ""

    if account_stability:
        details += "<b>📊 Account Stability</b>\n"
        for name, value in account_stability:
            details += f"• {name}: <b>{value}</b>\n"
        details += "\n"

    if transaction_patterns:
        details += "<b>💳 Transaction Patterns</b>\n"
        for name, value in transaction_patterns:
            details += f"• {name}: <b>{value}</b>\n"
        details += "\n"

    if affordability_metrics:
        details += "<b>💰 Affordability</b>\n"
        for name, value in affordability_metrics:
            details += f"• {name}: <b>{value}</b>\n"

    if not details:
        details = "<i>No factor breakdown available.</i>"

    return f"<b>🧾 Score Breakdown</b>\n\n{details}"


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
        step = state.get("step") or S_MENU  # Default to S_MENU if step is missing
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
            elif step == S_TIPS or step == S_DETAILS:
                # Handle callbacks when viewing tips or details
                # These steps only have back/cancel, which are handled above
                # But if any other callback comes through, send them back to menu
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "Please choose an option from the menu.",
                    kb_score_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                set_step(fsm, msg.chat_id, CMD, S_MENU, data)
                return
            # Unknown callback
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "Please choose an option from the menu.",
                kb_score_menu(),
                data=data,
            )
            return

        # Handle text messages (non-callback) when in flow
        # If user sends text while in S_TIPS or S_DETAILS, show the menu again
        if step == S_TIPS:
            set_step(fsm, msg.chat_id, CMD, S_MENU, data)
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "<b>💎 Score Dashboard</b>\n\nGet your score, tier, and see detailed breakdowns.",
                kb_score_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        elif step == S_DETAILS:
            set_step(fsm, msg.chat_id, CMD, S_MENU, data)
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "<b>💎 Score Dashboard</b>\n\nGet your score, tier, and see detailed breakdowns.",
                kb_score_menu(),
                data=data,
                parse_mode="HTML",
            )
            return

        # Fallback: reset flow
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please use /score to start again.")
