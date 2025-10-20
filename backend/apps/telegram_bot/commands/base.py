from backend.apps.telegram_bot.messages import TelegramMessage
from celery import shared_task
from typing import Any, Dict
from abc import ABC, abstractmethod
# Base command
class BaseCommand(ABC):
    name: str = ""
    description: str = ""
    permission: str = "public"  # e.g. "public", "borrower", "lender", "admin"
    def __init__(self):
        self.name = getattr(self, "name", "")
        self.description = getattr(self, "description", "")
        self.permission = getattr(self, "permission", "")

    # This function does validation on the message before enqueueing.
    @abstractmethod
    def handle(self, message: TelegramMessage) -> None:
        raise NotImplementedError("Handle method must be implemented by sub-classes")

    @staticmethod
    def serialize(message: TelegramMessage) -> Dict[str, Any]:
        return message.to_payload()

    @abstractmethod
    def task(self, message_data: dict) -> None:
        raise NotImplementedError("Task method must be implemented by sub-classes")
    

