from __future__ import annotations
from typing import Dict, Optional

from celery import shared_task

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
from backend.apps.telegram_bot.keyboards import kb_back_cancel

from backend.apps.tokens.models import CreditTrustBalance
from backend.apps.users.models import TelegramUser
from backend.apps.tokens.services.tier_calculation import TokenTierCalculator

# -------- Flow config --------
CMD = "tokens"

S_MENU = "tokens_menu"
S_BALANCE = "tokens_view_balance"
S_TIER = "tokens_view_tier"

PREV: Dict[str, Optional[str]] = {
    S_MENU: None,
    S_BALANCE: S_MENU,
    S_TIER: S_MENU,
}


def kb_tokens_menu() -> dict:
    """Keyboard for the tokens main menu."""
    return {
        "inline_keyboard": [
            [{"text": "💰 View Balance", "callback_data": "tokens:view_balance"}],
            [{"text": "📊 View Tier & APR", "callback_data": "tokens:view_tier"}],
            [
                {"text": "⬅️ Back", "callback_data": "flow:cancel"},
            ],
        ]
    }


@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="Check your CTT dashboard",
    permission="verified_borrower",
)
class TokenCommand(BaseCommand):
    """Displays CTT token balance and tier information."""

    name = CMD
    description = "Check your CTT dashboard"
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
            data = {}
            start_flow(fsm, msg.chat_id, CMD, data, S_MENU)
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "💎 <b>CTT Dashboard</b>\n\n"
                "Welcome to your Credit Trust Token dashboard!\n\n"
                "Choose an option below:",
                kb_tokens_menu(),
                data=data,
                parse_mode="HTML",
            )
            return

        # Guard: other command owns this chat
        if state.get("command") != CMD:
            return

        step = state.get("step")
        data = state.get("data", {}) or {}

        # --- Callbacks: cancel/back + menu actions ---
        cb = getattr(msg, "callback_data", None)
        if cb:
            if cb == "flow:cancel":
                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "👋 Exiting CTT dashboard. Use /tokens to return anytime.",
                    data=data,
                )
                return

            if cb == "flow:back":
                prev = prev_step_of(PREV, step)
                if prev is None:
                    # Back from main menu = exit
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(msg, "👋 Exiting CTT dashboard.", data=data)
                    return
                # Go back to previous step
                set_step(fsm, msg.chat_id, CMD, prev, data)
                mark_prev_keyboard(data, msg)
                if prev == S_MENU:
                    reply(
                        msg,
                        "💎 <b>CTT Dashboard</b>\n\n"
                        "Welcome to your Credit Trust Token dashboard!\n\n"
                        "Choose an option below:",
                        kb_tokens_menu(),
                        data=data,
                        parse_mode="HTML",
                    )
                return

            # Menu actions
            if step == S_MENU:
                if cb == "tokens:view_balance":
                    user = TelegramUser.objects.get(telegram_id=msg.user_id)
                    balance_record, _ = CreditTrustBalance.objects.get_or_create(
                        user=user
                    )
                    balance = balance_record.balance

                    set_step(fsm, msg.chat_id, CMD, S_BALANCE, data)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        f"💰 <b>Your CTT Balance</b>\n\n"
                        f"<b>Balance:</b> {balance:,.2f} CTT\n\n"
                        f"<i>Credit Trust Tokens represent your creditworthiness "
                        f"and unlock better loan terms.</i>",
                        kb_back_cancel(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                if cb == "tokens:view_tier":
                    user = TelegramUser.objects.get(telegram_id=msg.user_id)
                    balance_record, _ = CreditTrustBalance.objects.get_or_create(
                        user=user
                    )
                    balance = balance_record.balance
                    tier_info = TokenTierCalculator(balance).get_tier()

                    tier_message = (
                        f"📊 <b>Your Tier Information</b>\n\n"
                        f"<b>Current Tier:</b> {tier_info['tier']}\n"
                        f"<b>Max Loan Amount:</b> R{tier_info['max_loan']:,.2f}\n"
                        f"<b>Base APR:</b> {tier_info['base_apr']:.2f}%\n\n"
                        f"<i>Higher tiers unlock larger loans and better interest rates. "
                        f"Earn more CTT by repaying loans on time!</i>"
                    )

                    set_step(fsm, msg.chat_id, CMD, S_TIER, data)
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        tier_message,
                        kb_back_cancel(),
                        data=data,
                        parse_mode="HTML",
                    )
                    return

                # Unknown callback in menu
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "Please choose an option using the buttons below:",
                    kb_tokens_menu(),
                    data=data,
                )
                return

            # Callbacks in balance or tier view
            if step in (S_BALANCE, S_TIER):
                # Shouldn't reach here unless unknown callback
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "Please use the Back button to return to the menu.",
                    kb_back_cancel(),
                    data=data,
                )
                return

            # Unknown callback
            mark_prev_keyboard(data, msg)
            reply(msg, "Unsupported action. Please use the buttons.", data=data)
            return

        # --- Text input (user typed instead of using buttons) ---
        text = (msg.text or "").strip()

        if step == S_MENU:
            # User typed instead of using menu buttons
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "Please choose an option using the buttons below:",
                kb_tokens_menu(),
                data=data,
            )
            return

        if step in (S_BALANCE, S_TIER):
            # User typed instead of pressing back
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "Please use the Back button to return to the menu.",
                kb_back_cancel(),
                data=data,
            )
            return

        # Fallback
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please use /tokens to start again.")
