from __future__ import annotations

from typing import Dict, Optional, List, Dict as DictType
from celery import shared_task

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.flow import (
    start_flow,
    clear_flow,
    mark_prev_keyboard,
    reply,
)
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register

# Command + steps
CMD = "buyftc"

#TODO For lender, this comes later.

# ---------------------------
# BuyFTCCommand
# ---------------------------


@register(
    name=CMD, aliases=["/buyftc"], description="Buy FTC", permission="verified_lender"
)
class BuyFTCCommand(BaseCommand):
    name = CMD
    description = "Buy FTC"
    permission = "verified_lender"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(msg.chat_id)

        # Start menu if no state
        if not state:
            data = {}
            start_flow(fsm, msg.chat_id, CMD, data, S_MENU)
            # Initial header + menu
            reply(msg, intro_header(), kb_help_menu(), data=data)
            return

        # Guard: only handle our own flow
        if state.get("command") != CMD:
            return

        step = state.get("step") or S_MENU
        data = state.get("data", {}) or {}
        cb = getattr(msg, "callback_data", None)
        text = (msg.text or "").strip()

        # Always clear previous keyboard if present
        mark_prev_keyboard(data, msg)

        # Navigate back to menu
        if cb == CB_MENU:
            start_flow(fsm, msg.chat_id, CMD, data, S_MENU)
            reply(msg, intro_header(), kb_help_menu(), data=data)
            return

        # Main menu actions (callbacks)
        if cb and cb.startswith(CB_CAT):
            cat = cb.split(CB_CAT, 1)[1]
            if cat == CAT_FTC:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_FTC)
                reply(msg, render_ftc_category(), kb_ftc(), data=data)
                return
            if cat == CAT_FEES:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_FEES)
                reply(msg, render_fees_category(), kb_fees(), data=data)
                return
            if cat == CAT_LOAN:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_LOAN)
                reply(msg, render_loan_category(), kb_simple_back(), data=data)
                return
            if cat == CAT_REPAY:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_REPAY)
                reply(msg, render_repay_category(), kb_simple_back(), data=data)
                return
            if cat == CAT_SCORE:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_SCORE)
                reply(msg, render_score_category(), kb_simple_back(), data=data)
                return
            if cat == CAT_GENERAL:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_GENERAL)
                reply(msg, render_general_category(), kb_simple_back(), data=data)
                return

        # Q&A inside categories
        if cb and cb.startswith(CB_Q):
            # Re-render the category header + the specific answer, then keep its keyboard
            answer = render_answer(cb)
            if step == S_CAT_FTC:
                reply(
                    msg,
                    f"{render_ftc_category()}\n\n*Q&A*\n{answer}",
                    kb_ftc(),
                    data=data,
                )
                return
            if step == S_CAT_FEES:
                reply(
                    msg,
                    f"{render_fees_category()}\n\n*Q&A*\n{answer}",
                    kb_fees(),
                    data=data,
                )
                return
            # For other categories just show the answer with back
            reply(msg, answer, kb_simple_back(), data=data)
            return

        # if user pressed cancel/close
        if cb == "flow:cancel":
            clear_flow(fsm, msg.chat_id)
            reply(msg, "Help session closed. Use /help to start again.", data=data)
            return

        # If user typed anything instead of tapping
        if step == S_MENU:
            reply(msg, intro_header(), kb_help_menu(), data=data)
            return

        # In a subcategory, any text → show same subcategory content again
        if step == S_CAT_FTC:
            reply(msg, render_ftc_category(), kb_ftc(), data=data)
            return
        if step == S_CAT_FEES:
            reply(msg, render_fees_category(), kb_fees(), data=data)
            return
        if step == S_CAT_LOAN:
            reply(msg, render_loan_category(), kb_simple_back(), data=data)
            return
        if step == S_CAT_REPAY:
            reply(msg, render_repay_category(), kb_simple_back(), data=data)
            return
        if step == S_CAT_SCORE:
            reply(msg, render_score_category(), kb_simple_back(), data=data)
            return
        if step == S_CAT_GENERAL:
            reply(msg, render_general_category(), kb_simple_back(), data=data)
            return

        # Fallback → reset
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please /help again.")
