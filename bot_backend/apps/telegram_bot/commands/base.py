from bot_backend.apps.telegram_bot.messages import TelegramMessage
from celery import shared_task
from typing import Any, Dict
from abc import ABC, abstractmethod
# Base command
class BaseCommand(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    # abstract handle method
    def handle(self, message: TelegramMessage) -> None:
        raise NotImplementedError("Handle method must be implemented by sub-classes")

    @staticmethod
    def serialize(message: TelegramMessage) -> Dict[str, Any]:
        return message.to_payload()

    @shared_task(queue="telegram_bot")
    def task(self, message_data: dict) -> None:
        raise NotImplementedError("Task method must be implemented by sub-classes")


