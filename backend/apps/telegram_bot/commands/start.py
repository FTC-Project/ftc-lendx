from __future__ import annotations

import os
from typing import Dict, Optional
from celery import shared_task

from backend.apps.telegram_bot.commands.help import HelpCommand
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
from backend.apps.telegram_bot.keyboards import kb_accept_decline

from backend.apps.users.models import TelegramUser


# -------- Flow config --------
CMD = "start"
S_TOS = "awaiting_accept_TOS"

PREV: Dict[str, Optional[str]] = {
    S_TOS: None,
}


@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="Welcome/Onboarding",
    permission="public",
)
class StartCommand(BaseCommand):
    name = CMD
    description = "Welcome/Onboarding"
    permission = "public"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(msg.chat_id)

        # If already signed up, short-circuit
        user = TelegramUser.objects.filter(telegram_id=msg.user_id).first()
        if user and user.is_active:
            clear_flow(fsm, msg.chat_id)
            reply(msg, "You're already signed up. Use /help to see commands.")
            return

        # --- Start flow ---
        if not state:
            # Get TOS URL
            public_url = os.getenv("PUBLIC_URL", "")
            tos_url = f"{public_url.rstrip('/')}/tos/" if public_url else "#"

            welcome = (
                "Welcome to Nkadime! 🌟\n\n"
                "We help you access affordable credit using your banking data.\n"
                "All loans are in FTCoin (FTC), our stable digital currency.\n"
                "1 FTC = 1 ZAR always.\n\n"
                f"Before we get started, you'll need to accept our Terms of Service. "
                f"Read them here: {tos_url}\n\n"
                "Do you accept the Terms of Service?"
            )
            # Ask ToS
            data = {"accepted_tos": False}
            start_flow(fsm, msg.chat_id, CMD, data, S_TOS)
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                welcome,
                kb_accept_decline(),
                data=data,
            )
            return

        # Guard: other command owns this chat
        if state.get("command") != CMD:
            return

        step = state.get("step")
        data = state.get("data", {}) or {}

        cb = getattr(msg, "callback_data", None)

        # --- Only step in this flow: ToS accept/decline ---
        if step == S_TOS:
            if cb == "flow:accept":
                # User accepted TOS -> Create account once, then show help
                user, created = TelegramUser.objects.get_or_create(
                    telegram_id=msg.user_id,
                    defaults={
                        "username": msg.username,
                        "chat_id": msg.chat_id,
                        "first_name": msg.first_name,
                        "last_name": msg.last_name,
                        "is_active": True,
                    },
                )
                # We only care that it exists now; mark & clear flow
                mark_prev_keyboard(data, msg)
                clear_flow(fsm, msg.chat_id)

                # Confirm + show quick help
                welcome_message = (
                    "✅ <b>Thanks for accepting the Terms of Service!</b>\n"
                    "Your account has been created.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🌟 <b>Welcome to Nkadime!</b>\n\n"
                    "We help you access affordable credit using your banking data.\n"
                    "We also allow you to be a lender and earn interest on your deposits.\n\n"
                    "💵 <b>1 FTC = 1 ZAR always</b>\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "📋 <b>Get Started:</b>\n\n"
                    "To begin, we'll need to verify you and have you select a role.\n"
                    "You can do this by using the /register command.\n\n"
                    "💡 <i>Otherwise, you can use the /help command to see all available commands and some FAQs.</i>"
                )
                reply(
                    msg,
                    welcome_message,
                    data=data,
                    parse_mode="HTML",
                )
                return

            if cb == "flow:decline":
                # Declined TOS -> do NOT create a user; end flow
                mark_prev_keyboard(data, msg)
                clear_flow(fsm, msg.chat_id)
                reply(
                    msg,
                    "❌ You declined the Terms of Service. We can't proceed without acceptance.\n"
                    "If you change your mind, run /start again.",
                )
                return

            # If user typed or unknown callback, gently re-prompt
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "Please choose an option below to continue:",
                kb_accept_decline(),
                data=data,
            )
            return

        # Safety fallback: reset flow
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please /start again.")
