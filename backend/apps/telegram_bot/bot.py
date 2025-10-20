import os
from typing import Dict, Optional

from functools import lru_cache

from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.registry import all_command_metas, get_command_meta
from backend.apps.telegram_bot.tasks import send_telegram_message_task

from .messages import TelegramMessage


class TelegramBot:
    """Dispatch Telegram commands and talk to the Bot API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
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
        command = self.get_command(msg.command)
        if command:
            if self.has_permission(command.meta, msg):
                command.handle(msg)
            else:
                print(
                    f"[bot] User {msg.user_id} is not authorized to use {msg.command}"
                )
        else:
            print(f"[bot] Unknown command '{msg.command}'")

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
        command = self.get_command(cmd_name)
        if command:
            if self.has_permission(command.meta, msg):
                command.handle(msg)
            else:
                print(f"[bot] User {msg.user_id} is not authorized to use {cmd_name}")
        else:
            print(f"[bot] Unknown command '{cmd_name}' in FSM")

    def has_permission(self, meta: Optional[object], msg: TelegramMessage) -> bool:
        """Check if the user has permission to run the command."""
        if not meta:
            return False
        # For now, all commands are public, in future will check user role
        return True


@lru_cache(maxsize=1)
def get_bot(token: Optional[str] = None) -> TelegramBot:
    """Return a singleton TelegramBot instance."""
    return TelegramBot(token)
