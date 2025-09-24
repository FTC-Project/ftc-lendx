from __future__ import annotations

from typing import Any, Dict, List, Optional

from celery import shared_task
from xrpl.utils import xrp_to_drops

from bot_backend.apps.users.crypto import decrypt_secret, encrypt_secret
from bot_backend.apps.users.models import TelegramUser, Transfer, Wallet
from bot_backend.apps.users.xrpl_service import create_user_wallet, get_balance, send_xrp

from .bot import bot
from .messages import TelegramMessage


def _build_message(payload: Dict[str, Any]) -> TelegramMessage:
    args: Optional[List[str]] = payload.get("args")
    if args is None:
        payload = {**payload, "args": []}
    return TelegramMessage(**payload)


def handle_message(message: TelegramMessage) -> None:
    """Dispatch an incoming Telegram command."""
    bot.handle_message(message)


@shared_task(queue="telegram_bot")
def start_command_task(message_data: Dict[str, Any]) -> None:
    msg = _build_message(message_data)
    print(f"Processing /start for user {msg.user_id}")

    try:
        user, created = TelegramUser.objects.get_or_create(
            telegram_id=msg.user_id,
            defaults={
                "username": msg.username,
                "first_name": msg.first_name,
                "last_name": msg.last_name,
                "is_active": True,
            },
        )
        if created:
            welcome_text = (
                f"🚀 Welcome to XRPL Bot, {msg.first_name or 'friend'}!\n\n"
                "I'll help you manage XRP on the XRPL TestNet.\n\n"
                "We created your account. You can use /help to see available commands."
            )
        else:
            welcome_text = (
                f"🚀 Welcome back, {msg.first_name or 'friend'}!\n\n"
                "Use /help to see available commands."
            )

        bot.send_message(msg.chat_id, welcome_text)
        print(f"START completed for user {user.telegram_id}")
    except Exception as exc:
        print(f"Error in start command: {exc}")
        bot.send_message(msg.chat_id, "Sorry, something went wrong during setup!")


@shared_task(queue="telegram_bot")
def help_command_task(message_data: Dict[str, Any]) -> None:
    msg = _build_message(message_data)
    help_text = (
        "📋 Available Commands:\n\n"
        "/start - Get started with the bot\n"
        "/balance - Check your XRP balance\n"
        "/send @username amount - Send XRP to another user\n"
        "/prices [days] - Get XRP price data (default: 30 days)\n"
        "/wallet - Create a new XRPL wallet\n"
        "/help - Show this help message\n\n"
        "Example: /send @alice 10.5"
    )
    bot.send_message(msg.chat_id, help_text)


@shared_task(queue="telegram_bot")
def balance_command_task(message_data: Dict[str, Any]) -> None:
    msg = _build_message(message_data)
    print(f"Processing /balance for user {msg.user_id}")

    try:
        try:
            user = TelegramUser.objects.get(telegram_id=msg.user_id)
        except TelegramUser.DoesNotExist:
            bot.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
            return

        if not hasattr(user, "wallet"):
            bot.send_message(msg.chat_id, "❌ You don't have a wallet yet. Use /wallet to create one.")
            return

        wallet_address = Wallet.objects.get(user=user).address
        balance = get_balance(wallet_address)

        if balance is None:
            bot.send_message(msg.chat_id, "❌ Could not retrieve balance. Please try again later.")
            return

        bot.send_message(msg.chat_id, f"💰 Your balance: {balance} XRP")
        print(f"Balance response sent for user {msg.user_id}")
    except Exception as exc:
        print(f"Error in balance command: {exc}")
        bot.send_message(msg.chat_id, "❌ Could not retrieve balance. Please try again later.")


@shared_task(queue="telegram_bot")
def send_command_task(message_data: Dict[str, Any]) -> None:
    msg = _build_message(message_data)
    print(f"Processing /send from user {msg.user_id}")

    args = msg.args or []
    if len(args) < 2:
        bot.send_message(
            msg.chat_id,
            "Usage: /send @username amount\nExample: /send @alice 10.5",
        )
        return

    recipient_username = args[0].lstrip("@")

    try:
        amount = float(args[1])
    except ValueError:
        bot.send_message(msg.chat_id, "❌ Invalid amount. Please enter a valid number.")
        return

    if amount <= 0:
        bot.send_message(msg.chat_id, "❌ Amount must be greater than 0")
        return

    try:
        if recipient_username.lower() == (msg.username or "").lower():
            bot.send_message(msg.chat_id, "❌ You cannot send XRP to yourself.")
            return

        try:
            sender = TelegramUser.objects.get(telegram_id=msg.user_id)
        except TelegramUser.DoesNotExist:
            bot.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
            return

        if not hasattr(sender, "wallet"):
            bot.send_message(msg.chat_id, "❌ You don't have a wallet yet. Use /wallet to create one.")
            return

        try:
            recipient = TelegramUser.objects.get(username__iexact=recipient_username)
        except TelegramUser.DoesNotExist:
            bot.send_message(msg.chat_id, f"❌ User @{recipient_username} not found.")
            return

        if not hasattr(recipient, "wallet"):
            bot.send_message(msg.chat_id, f"❌ User @{recipient_username} does not have a wallet yet.")
            return

        sender_wallet = Wallet.objects.get(user=sender)
        recipient_wallet = Wallet.objects.get(user=recipient)

        sender_balance = get_balance(sender_wallet.address)
        if sender_balance is None or sender_balance < amount:
            bot.send_message(msg.chat_id, "❌ Insufficient balance.")
            return

        transfer = Transfer.objects.create(
            status="pending",
            sender=sender,
            recipient=recipient,
            destination_address=recipient_wallet.address,
            amount_drops=int(xrp_to_drops(amount)),
        )
        bot.send_message(msg.chat_id, f"⏳ Sending {amount} XRP to @{recipient_username}...")

        tx_hash = send_xrp(
            decrypt_secret(sender_wallet.secret_encrypted.tobytes()),
            recipient_wallet.address,
            amount,
        )

        if not tx_hash:
            transfer.tx_hash = None
            transfer.status = "failed"
            transfer.save()
            bot.send_message(msg.chat_id, "❌ Transaction failed. Please try again later.")
            return

        transfer.tx_hash = tx_hash
        transfer.status = "validated"
        transfer.save()
        print(
            f"Sent {amount} XRP from {sender.telegram_id} to {recipient.telegram_id}, TX: {tx_hash}",
        )

        bot.send_message(
            msg.chat_id,
            f"✅ Sent {amount} XRP to @{recipient_username}!\nTX Hash: {tx_hash}",
        )
    except Exception as exc:
        print(f"Error in send command: {exc}")
        bot.send_message(msg.chat_id, f"❌ Failed to send XRP: {exc}")


@shared_task(queue="telegram_bot")
def prices_command_task(message_data: Dict[str, Any]) -> None:
    msg = _build_message(message_data)
    args = msg.args or []
    days = 30

    if args:
        try:
            days = int(args[0])
            days = max(1, min(days, 365))
        except ValueError:
            bot.send_message(msg.chat_id, "❌ Invalid number of days. Using default (30).")
            days = 30

    try:
        bot.send_message(
            msg.chat_id,
            f"📈 XRP prices for the last {days} days:\n[Price API integration coming soon]",
        )
    except Exception as exc:
        print(f"Error in prices command: {exc}")
        bot.send_message(msg.chat_id, "❌ Could not fetch price data. Please try again later.")


@shared_task(queue="telegram_bot")
def wallet_command_task(message_data: Dict[str, Any]) -> None:
    msg = _build_message(message_data)
    print(f"Processing /wallet for user {msg.user_id}")

    try:
        try:
            user = TelegramUser.objects.get(telegram_id=msg.user_id)
        except TelegramUser.DoesNotExist:
            bot.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
            return

        if hasattr(user, "wallet"):
            bot.send_message(msg.chat_id, "❌ You already have a wallet.")
            return

        gen_wallet = create_user_wallet()
        Wallet.objects.create(
            user=user,
            network="testnet",
            address=gen_wallet.classic_address,
            secret_encrypted=encrypt_secret(gen_wallet.seed),
        )

        bot.send_message(
            msg.chat_id,
            (
                "🆕 Wallet created!\n"
                f"Address: {gen_wallet.classic_address}\n"
                "You have been credited with test XRP.\n"
                "Use /balance to check your balance."
            ),
        )
        print(f"Wallet created for user {user.telegram_id}: {gen_wallet.classic_address}")
    except Exception as exc:
        print(f"Error in wallet command: {exc}")
        bot.send_message(msg.chat_id, "❌ Could not create wallet. Please try again later.")
