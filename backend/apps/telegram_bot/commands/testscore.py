from __future__ import annotations

from celery import shared_task

from backend.apps.banking.models import BankAccount
from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.flow import reply

from backend.apps.users.models import TelegramUser
from backend.apps.scoring.tasks import start_scoring_pipeline


@register(
    name="testscore",
    aliases=["/testscore"],
    description="Trigger scoring for the first user and their bank account",
    permission="public",
)
class TestScoreCommand(BaseCommand):
    name = "testscore"
    description = "Trigger scoring for the first user and their bank account"
    permission = "public"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))
        

    
    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        message = TelegramMessage.from_payload(message_data)
        # Find the first user in the DB
        user = TelegramUser.objects.first()
        if not user:
            reply(message, "No users found in the database.")
            return

        # Try to get a bank account for that user; fall back to any bank account if none found for user
        bank_account = BankAccount.objects.filter(user=user).first()
        if not bank_account:
            bank_account = BankAccount.objects.first()
            if not bank_account:
                reply(message, "No bank accounts found in the database.")
                return

        try:
            # Queue the scoring pipeline task
            start_scoring_pipeline.delay(user.id, bank_account.id)
            reply(
                message,
                f"Scoring started for user id={user.id} and bank_account id={bank_account.id}.",
            )
        except Exception as e:
            reply(message, f"Failed to queue scoring task: {e}")

