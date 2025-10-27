import os
from typing import Dict, Optional

from functools import lru_cache

from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.registry import all_command_metas, get_command_meta
from backend.apps.telegram_bot.tasks import send_telegram_message_task, check_permission_and_dispatch_task

from django.conf import settings

from .messages import TelegramMessage


class TelegramBot:
    """Dispatch Telegram commands and talk to the Bot API."""

    def __init__(self):
        self.token = getattr(
            settings, "TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", "")
        )
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.command_instances: Dict[str, object] = {}
        self.command_metas = all_command_metas()
        self.fsm = FSMStore()

    def get_command(self, name: str) -> Optional[object]:
        inst = self.command_instances.get(name)
        if inst:
            return inst
        meta = self.command_metas.get(name) or get_command_meta(name)
        if not meta:
            return None
        inst = meta.cls()
        setattr(inst, "meta", meta)
        self.command_instances[meta.name] = inst
        # Cache by alias too, in case for alias lookup later
        for alias in meta.aliases:
            self.command_instances[alias] = inst
        return inst

    def dispatch_command(self, msg: TelegramMessage) -> None:
        """
        Non-blocking command dispatch.
        Enqueues permission check task which will then dispatch to command if authorized.
        """
        meta = self.command_metas.get(msg.command) or get_command_meta(msg.command)
        if not meta:
            print(f"[bot] Unknown command '{msg.command}'")
            return
        
        # Enqueue non-blocking permission check + dispatch
        check_permission_and_dispatch_task.delay(
            msg.to_payload(),
            meta.name,
            meta.permission
        )

    def handle_message(self, msg: TelegramMessage) -> None:
        """Schedule the matching command handler."""
        # First check if there is a command
        if msg.command and msg.command == "cancel":
            self.fsm.clear(msg.chat_id)
            send_telegram_message_task.delay(msg.chat_id, "❌ Cancelled.")
            return
        if msg.command:
            try:
                self.fsm.clear(msg.chat_id)
                # NOTE: For a command left dangling we just kill the previous flow
                return self.dispatch_command(msg)
            except Exception as exc:  # Never crash the bot
                print(f"[bot] Error while scheduling {msg.command}: {exc}")
        # If non command, check unfinished FSM
        state = self.fsm.get(msg.chat_id)
        if not state:
            return send_telegram_message_task.delay(
                msg.chat_id,
                "⚠️ Unrecognized command. Use /help to see available commands.",
            )
        # Otherwise route to the command handling the FSM
        cmd_name = state["command"]
        meta = self.command_metas.get(cmd_name) or get_command_meta(cmd_name)
        if not meta:
            print(f"[bot] Unknown command '{cmd_name}' in FSM")
            return
        
        # Enqueue non-blocking permission check + dispatch for FSM continuation
        check_permission_and_dispatch_task.delay(
            msg.to_payload(),
            meta.name,
            meta.permission
        )

    # NOTE: has_permission is no longer used - permission checks are now non-blocking
    # and handled by check_permission_and_dispatch_task in tasks.py


@lru_cache(maxsize=1)
def get_bot() -> TelegramBot:
    """Return a singleton TelegramBot instance."""
    return TelegramBot()
