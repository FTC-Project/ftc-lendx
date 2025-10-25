from django.db.models.signals import post_save
from django.dispatch import receiver

from backend.apps.telegram_bot.tasks import send_telegram_message_task
from .models import (
    TelegramUser,
    Notification,
)  # Assuming Notification is in users.models
from backend.apps.kyc.models import KYCVerification


# Make a KYC Verification Object with status pending when user object created
@receiver(
    post_save, sender=TelegramUser, dispatch_uid="users.signals.create_related_objects"
)
def create_user_related_objects(sender, instance, created, **kwargs):
    if created:
        # Create a KYC Verification Object
        KYCVerification.objects.create(user=instance, status="pending")


# When a Notification model is created, send a message to the user via Telegram
@receiver(
    post_save,
    sender=Notification,
    dispatch_uid="notifications.signals.send_notification",
)
def send_notification_on_creation(sender, instance, created, **kwargs):
    """Sends a Telegram message when a new Notification object is created."""
    if created:
        # First check if we have sent
        if instance.sent:
            return
        # Now we must use the `kind` to determine the message content
        if instance.kind == "score_updated":
            text = (
                f"Your trust score has been updated to {instance.payload['score']:.2f}"
                f"({instance.payload['risk']})."
            )
        else:
            # For other kinds, do not send a message
            return
        if instance.user and instance.user.chat_id:
            send_telegram_message_task.delay(chat_id=instance.user.chat_id, text=text)
        # Mark as sent
        instance.sent = True
        instance.save(update_fields=['sent'])
