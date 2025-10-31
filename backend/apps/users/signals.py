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

        text = None
        parse_mode = "HTML"  # Use HTML formatting for all messages

        # Now we must use the `kind` to determine the message content
        if instance.kind == "score_updated":
            score = instance.payload.get("score")
            tier = instance.payload.get("tier", "unknown")
            limit = instance.payload.get("limit")
            if score is not None:
                text = (
                    f"<b>🎯 Affordability Score Updated</b>\n\n"
                    f"Your affordability score has been updated to <b>{score:.2f}</b>. \n\n"
                    f"Your tier is <b>{tier}</b>. \n\n"
                    f"Your credit limit is <b>R{limit:,.2f}</b>. \n\n"
                    f"You can view a detailed breakdown of your score by using the /score command."
                )
            else:
                text = (
                    "<b>🎯 Affordability Score Updated</b>\n\n"
                    "Your affordability score has been updated, but the new score is unavailable."
                )

        elif instance.kind == "loan_created_on_chain":
            loan_id = instance.payload.get("loan_id")
            amount = instance.payload.get("amount")
            apr_bps = instance.payload.get("apr_bps")
            term_days = instance.payload.get("term_days")
            tx_hash = instance.payload.get("tx_hash")
            # Convert apr_bps to percentage (e.g., 2500 bps = 25.00%)
            apr_percent = apr_bps / 100 if apr_bps else 0

            text = (
                f"<b>✅ Loan Created On-Chain</b>\n\n"
                f"Your loan has been successfully created on the blockchain!\n\n"
                f"<b>Loan Details:</b>\n"
                f"🆔 Loan ID: <code>{loan_id}</code>\n"
                f"💰 Amount: <b>R{amount:,}</b>\n"
                f"📊 APR: <b>{apr_percent:.2f}%</b>\n"
                f"📅 Term: <b>{term_days} days</b>\n\n"
                f"🔗 Transaction Hash: <code>{tx_hash}</code>\n\n"
                f"<i>Your loan is now being processed for funding...</i>"
            )

        elif instance.kind == "loan_funded_on_chain":
            loan_id = instance.payload.get("loan_id")
            amount = instance.payload.get("amount")
            apr_bps = instance.payload.get("apr_bps")
            term_days = instance.payload.get("term_days")
            tx_hash = instance.payload.get("tx_hash")
            apr_percent = apr_bps / 100 if apr_bps else 0

            text = (
                f"<b>💎 Loan Funded On-Chain</b>\n\n"
                f"Great news! Your loan has been funded by the liquidity pool.\n\n"
                f"<b>Loan Details:</b>\n"
                f"🆔 Loan ID: <code>{loan_id}</code>\n"
                f"💰 Funded Amount: <b>R{amount:,}</b>\n"
                f"📊 APR: <b>{apr_percent:.2f}%</b>\n"
                f"📅 Term: <b>{term_days} days</b>\n\n"
                f"🔗 Transaction Hash: <code>{tx_hash}</code>\n\n"
                f"<i>Preparing for disbursement...</i>"
            )

        elif instance.kind == "loan_disbursed_on_chain":
            loan_id = instance.payload.get("loan_id")
            amount = instance.payload.get("amount")
            apr_bps = instance.payload.get("apr_bps")
            term_days = instance.payload.get("term_days")
            tx_hash = instance.payload.get("tx_hash")
            apr_percent = apr_bps / 100 if apr_bps else 0

            text = (
                f"<b>🎉 Loan Disbursed!</b>\n\n"
                f"Congratulations! Your loan has been successfully disbursed.\n\n"
                f"<b>Loan Summary:</b>\n"
                f"🆔 Loan ID: <code>{loan_id}</code>\n"
                f"💰 Disbursed Amount: <b>R{amount:,}</b>\n"
                f"📊 Interest Rate: <b>{apr_percent:.2f}% APR</b>\n"
                f"📅 Repayment Period: <b>{term_days} days</b>\n\n"
                f"🔗 Transaction Hash: <code>{tx_hash}</code>\n\n"
                f"<b>⚠️ Important:</b> Please ensure timely repayments to maintain your trust score.\n\n"
                f"<i>The funds are now available in your account.</i>"
            )

        elif instance.kind == "wallet_created":
            address = instance.payload.get("address")
            private_key = instance.payload.get("private_key")
            text = (
                f"<b>💰 Wallet Created </b>\n\n"
                f"Your wallet has been successfully created on the blockchain!\n\n"
                f"<b>Wallet Address:</b>\n"
                f"<code>{address}</code>\n\n"
                f"<b>Private Key:</b>\n<code>{private_key}</code>\n\n"
                f"⚠️ Please store your private key safely!"
            )

        else:
            # For other kinds, do not send a message
            return

        # Send the notification if we have text and a valid chat_id
        if text and instance.user and instance.user.chat_id:
            send_telegram_message_task.delay(
                chat_id=instance.user.chat_id, text=text, parse_mode=parse_mode
            )
        # Mark as sent
        instance.sent = True
        instance.save(update_fields=["sent"])
