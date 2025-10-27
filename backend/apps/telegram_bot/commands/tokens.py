from __future__ import annotations
from typing import Dict, Optional

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.commands.help import HelpCommand
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.flow import start_flow, clear_flow, mark_prev_keyboard, reply

from backend.apps.tokens.models import CreditTrustBalance
from backend.apps.users.models import TelegramUser
from backend.apps.telegram_bot.keyboards import kb_options, kb_back_cancel
from celery import shared_task

from backend.apps.tokens.services.tier_calculation import TokenTierCalculator

CMD = "tokens"
S_MENU = "tokens_menu"
S_BALANCE = "tokens_view_balance"
S_TIER = "tokens_view_tier"


PREV: Dict[str, Optional[str]] = {
    S_MENU: None,
    S_BALANCE: S_MENU,
    S_TIER: S_MENU
}

def kb_tokens_menu() -> dict:
    """Keyboard for the tokens main menu."""
    return kb_options([
        ("💰 View Balance", "tokens:view_balance"),
        ("📊 View Tier & APR", "tokens:view_tier"),
        
        ("⬅️ Back", "tokens:back"),
    ])

@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="Check your CTT dashboard",
    permission="public",
)
class TokenCommand(BaseCommand):
    name = CMD
    description = "Check your CTT dashboard"
    permission = "public"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        message = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(message.chat_id)
        cb = getattr(message, "callback_data", None)

        # If no state, start menu
        if not state:
            data = {}
            start_flow(fsm, message.chat_id, CMD, data, S_MENU)
            reply(message, "Welcome to your CTT dashboard! Choose an option:", kb_tokens_menu(), data=data)
            return

        # Guard: other command owns this chat
        if state.get("command") != CMD:
            return

        step = state.get("step")
        data = state.get("data", {}) or {}

        # --- Menu step ---
        if step == S_MENU:
            if cb == "tokens:view_balance":
                start_flow(fsm, message.chat_id, CMD, data, S_BALANCE)
                balance_record, _ = CreditTrustBalance.objects.get_or_create(user=user)
                balance = balance_record.balance
                reply(message, f"💰 Your CTT balance is: {balance} CTT", kb_back_cancel())
                return

            if cb == "tokens:view_tier":
                start_flow(fsm, message.chat_id, CMD, data, S_TIER)

                # Example tier logic: replace with actual tier calculation if available
                balance_record, _ = CreditTrustBalance.objects.get_or_create(user=user)
                balance = balance_record.balance
                tier_info = TokenTierCalculator(balance).get_tier()

                tier_message = (
                    f"📊 Current tier: \n"
                    f"{tier_info['tier']}\n"
                    f"\n"
                    f"💰 Max Loan: \n"
                    f"R{tier_info['max_loan']}\n"
                    f"\n"
                    f"📈 Base APR: \n"
                    f"{tier_info['base_apr']}%\n"
                )

                # Send reply to user
                reply(message, tier_message, kb_back_cancel())
                return
            
            
            
            if cb == "tokens:back":
                clear_flow(fsm, message.chat_id)
                HelpCommand().handle(message)
                return

            # Unknown input, re-show menu
            reply(message, "Please choose an option:", kb_tokens_menu(), data=data)
            return

        # --- Balance or Tier step ---
        if step in (S_BALANCE, S_TIER):
            # Any button press goes back to main menu
            clear_flow(fsm, message.chat_id)
            self.handle(message)
            return

        # Safety fallback
        clear_flow(fsm, message.chat_id)
        reply(message, "Session lost. Please /tokens again.")
