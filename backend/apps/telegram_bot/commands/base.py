from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from typing import Any, Dict
from abc import ABC, abstractmethod

from backend.apps.telegram_bot.tasks import send_telegram_message_task


# Base command
class BaseCommand(ABC):
    name: str = ""
    description: str = ""
    permission: str = "public"  # e.g. "public", "borrower", "lender", "admin"

    def __init__(self):
        self.fsm = FSMStore()

    # This function does validation on the message before enqueueing.
    @abstractmethod
    def handle(self, message: TelegramMessage) -> None:
        raise NotImplementedError("Handle method must be implemented by sub-classes")

    @staticmethod
    def serialize(message: TelegramMessage) -> Dict[str, Any]:
        return message.to_payload()

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> TelegramMessage:
        return TelegramMessage.from_payload(data)

    @abstractmethod
    def task(self, message_data: dict) -> None:
        raise NotImplementedError("Task method must be implemented by sub-classes")

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
