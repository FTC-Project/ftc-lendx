from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from typing import Any, Dict
from abc import ABC, abstractmethod

from backend.apps.telegram_bot.tasks import send_telegram_message_task


# Base command
class BaseCommand(ABC):
    """
    Base class for all Telegram bot commands.
    
    Commands should:
    1. Implement handle() to delegate to a Celery task
    2. Define a @shared_task decorated task() function
    3. Set name, description, and permission class attributes
    
    The permission check is handled non-blocking by check_permission_and_dispatch_task.
    """
    name: str = ""
    description: str = ""
    permission: str = "public"  # e.g. "public", "user", "borrower", "verified_borrower", etc.
    
    # task should be a @shared_task decorated function, not an instance method
    task = None

    def __init__(self):
        self.fsm = FSMStore()

    @abstractmethod
    def handle(self, message: TelegramMessage) -> None:
        """
        Handle incoming message by delegating to Celery task.
        Typically: self.task.delay(self.serialize(message))
        """
        raise NotImplementedError("Handle method must be implemented by sub-classes")

    @staticmethod
    def serialize(message: TelegramMessage) -> Dict[str, Any]:
        return message.to_payload()

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> TelegramMessage:
        return TelegramMessage.from_payload(data)

    def ask_and_wait(
        self,
        chat_id: int,
        question: str,
        step: str,
        data: dict = None,
        reply_markup: dict = None,
    ):
        """Send a question to the user and set FSM state to wait for response."""
        with self.fsm.lock(chat_id):
            self.fsm.set(chat_id, self.name, step, data or {})
        send_telegram_message_task.delay(chat_id, question, reply_markup)

    def clear_flow(self, chat_id: int, final_message: str = None):
        """Clear the FSM state for the user."""
        with self.fsm.lock(chat_id):
            self.fsm.clear(chat_id)
        if final_message:
            send_telegram_message_task.delay(chat_id, final_message)
