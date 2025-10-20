import os
from typing import Dict, Optional

from functools import lru_cache

from backend.apps.telegram_bot.registry import all_command_metas, get_command_meta

from .messages import TelegramMessage



class TelegramBot:
    """Dispatch Telegram commands and talk to the Bot API."""
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.command_instances: Dict[str, object] = {}
        self.command_metas = all_command_metas()

    def get_command(self, name: str) -> Optional[object]:
        inst = self.command_instances.get(name)
        if inst:
            return inst
        meta = self.command_metas.get(name) or get_command_meta(name)
        if not meta:
            return None
        inst = meta.cls()
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
                print(f"[bot] User {msg.user_id} is not authorized to use {msg.command}")
        else:
            print(f"[bot] Unknown command '{msg.command}'")

    def handle_message(self, msg: TelegramMessage) -> None:
        """Schedule the matching command handler."""
        print(f"[bot] Dispatching command '{msg.command}' for user {msg.user_id}") # convert to logger later TODO
        try:
            self.dispatch_command(msg)
        except Exception as exc:  # Never crash the bot
            print(f"[bot] Error while scheduling {msg.command}: {exc}")
            # Just chill

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
