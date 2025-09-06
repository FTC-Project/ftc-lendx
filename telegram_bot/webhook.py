import os
import json
import requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from typing import Optional, Dict, Any
from dataclasses import dataclass
from bot_backend.apps.users.models import TelegramUser, Wallet
from bot_backend.apps.users.xrpl_service import create_user_wallet

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_URL = f"https://api.telegram.org/bot{TOKEN}"


@dataclass
class TelegramMessage:
    """Clean data structure for incoming messages."""
    chat_id: int
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    text: str
    command: Optional[str] = None
    args: list = None

    def __post_init__(self):
        if self.text.startswith('/'):
            parts = self.text.split()
            self.command = parts[0][1:].lower()  # Remove '/' and lowercase
            self.args = parts[1:] if len(parts) > 1 else []


class TelegramBot:
    """Core bot logic - simple and synchronous for clarity."""

    def __init__(self):
        self.api_url = API_URL
        print(f"🤖 Bot initialized with API: {self.api_url[:50]}...")

    def send_message(self, chat_id: int, text: str, parse_mode: Optional[str] = None) -> bool:
        """Send a message via Telegram Bot API - simple and sync."""
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            print(f"✅ Message sent to {chat_id}: {text[:50]}...")
            return True
        except requests.RequestException as e:
            print(f"❌ Error sending message to {chat_id}: {e}")
            return False

    def handle_message(self, msg: TelegramMessage):
        """Route message to appropriate handler - simple sync dispatch."""
        print(f"🔍 Processing command: {msg.command} from user {msg.user_id}")
        try:
            if msg.command == 'start':
                self.cmd_start(msg)
            elif msg.command == 'help':
                self.cmd_help(msg)
            elif msg.command == 'balance':
                self.cmd_balance(msg)
            elif msg.command == 'send':
                self.cmd_send(msg)
            elif msg.command == 'prices':
                self.cmd_prices(msg)
            elif msg.command == 'wallet':
                self.cmd_wallet(msg)
            else:
                self.send_message(msg.chat_id, "Unknown command. Try /help for available commands.")

            print(f"✅ Command {msg.command} completed successfully")

        except Exception as e:
            print(f"❌ Error processing command {msg.command}: {e}")
            self.send_message(msg.chat_id, f"❌ Sorry, something went wrong: {str(e)}")

    def cmd_start(self, msg: TelegramMessage):
        """Handle /start command - create user if needed."""
        print(f"🔍 START command for user {msg.user_id}")
        try:
            user, created = TelegramUser.objects.get_or_create(
                telegram_id=msg.user_id,
                defaults={
                    'username': msg.username,
                    'first_name': msg.first_name,
                    'last_name': msg.last_name,
                    'is_active': True,
                }
            )
            print(f"🔍 User {'created' if created else 'found'}: {user.telegram_id}")
            if created:
                welcome_text = f"""🚀 Welcome to XRPL Bot, {msg.first_name or 'friend'}!

I'll help you manage XRP on the XRPL TestNet.

We created your account. You can use /help to see available commands."""
            else:
                welcome_text = f"""🚀 Welcome back, {msg.first_name or 'friend'}!

Use /help to see available commands."""

            self.send_message(msg.chat_id, welcome_text)
            print("🔍 START command completed")

        except Exception as e:
            print(f"❌ Error in cmd_start: {e}")
            self.send_message(msg.chat_id, "Sorry, something went wrong during setup!")

    def cmd_help(self, msg: TelegramMessage):
        """Show available commands."""
        help_text = """📋 Available Commands:

/start - Get started with the bot
/balance - Check your XRP balance  
/send @username amount - Send XRP to another user
/prices [days] - Get XRP price data (default: 30 days)
/help - Show this help message

Example: /send @alice 10.5"""

        self.send_message(msg.chat_id, help_text)

    def cmd_balance(self, msg: TelegramMessage):
        """Check user's XRP balance."""
        try:
            # TODO: Get user's wallet from database
            # user = TelegramUser.objects.get(telegram_id=msg.user_id)
            # wallet_address = user.wallet.address if user.wallet else None
            # balance = get_xrp_balance_sync(wallet_address)

            # Placeholder for now
            balance = 0.0
            self.send_message(msg.chat_id, f"💰 Your balance: {balance} XRP")

        except TelegramUser.DoesNotExist:
            self.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
        except Exception as e:
            print(f"❌ Error in cmd_balance: {e}")
            self.send_message(msg.chat_id, "❌ Could not retrieve balance. Please try again later.")

    def cmd_send(self, msg: TelegramMessage):
        """Send XRP to another user."""
        if not msg.args or len(msg.args) < 2:
            self.send_message(
                msg.chat_id,
                "Usage: /send @username amount\nExample: /send @alice 10.5"
            )
            return

        try:
            recipient_username = msg.args[0].lstrip('@')
            amount = float(msg.args[1])

            if amount <= 0:
                self.send_message(msg.chat_id, "❌ Amount must be greater than 0")
                return

            # TODO: Implement XRPL transaction
            # sender = TelegramUser.objects.get(telegram_id=msg.user_id)
            # recipient = TelegramUser.objects.get(username=recipient_username)
            # tx_hash = send_xrp_sync(sender.wallet, recipient.wallet.address, amount)

            # Placeholder response
            self.send_message(
                msg.chat_id,
                f"✅ Sent {amount} XRP to @{recipient_username}!\n"
                f"TX Hash: [XRPL integration coming soon]"
            )

        except ValueError:
            self.send_message(msg.chat_id, "❌ Invalid amount. Please enter a valid number.")
        except TelegramUser.DoesNotExist:
            if 'sender' not in locals():
                self.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
            else:
                self.send_message(msg.chat_id, f"❌ User @{recipient_username} not found.")
        except Exception as e:
            print(f"❌ Error in cmd_send: {e}")
            self.send_message(msg.chat_id, f"❌ Failed to send XRP: {str(e)}")

    def cmd_prices(self, msg: TelegramMessage):
        """Get XRP price data."""
        days = 30  # default

        if msg.args:
            try:
                days = int(msg.args[0])
                days = max(1, min(days, 365))  # Clamp between 1-365
            except ValueError:
                self.send_message(msg.chat_id, "❌ Invalid number of days. Using default (30).")

        try:
            # TODO: Implement price fetching
            # prices = fetch_xrp_prices_sync(days)
            # price_summary = format_price_data(prices)

            self.send_message(
                msg.chat_id,
                f"📈 XRP prices for the last {days} days:\n[Price API integration coming soon]"
            )

        except Exception as e:
            print(f"❌ Error in cmd_prices: {e}")
            self.send_message(msg.chat_id, "❌ Could not fetch price data. Please try again later.")

    def cmd_wallet(self, msg: TelegramMessage):
        """Create a new XRPL wallet for the user."""
        try:
            user = TelegramUser.objects.get(telegram_id=msg.user_id)
            if hasattr(user, 'wallet'):
                self.send_message(msg.chat_id, "❌ You already have a wallet.")
                return
            gen_wallet = create_user_wallet()
            # We now create the actual wallet in the DB
            Wallet.objects.create(
                user=user,
                network="testnet",
                address=gen_wallet.classic_address,
                secret_encrypted=gen_wallet.seed.encode()  # In real app, encrypt this!
            )
            print(f"🔍 Created wallet for user {user.telegram_id}: {gen_wallet.classic_address}")
            self.send_message(
                msg.chat_id,
                f"🆕 Wallet created!\nAddress: {gen_wallet.classic_address}\n"
                f"You have been credited with test XRP.\n"
                f"Use /balance to check your balance."
            )
        except TelegramUser.DoesNotExist:
            self.send_message(msg.chat_id, "❌ Please use /start first to create your account.")
        except Exception as e:
            print(f"❌ Error in cmd_create_wallet: {e}")
            self.send_message(msg.chat_id, "❌ Could not create wallet. Please try again later.")



# Global bot instance
bot = TelegramBot()


def parse_telegram_message(data: Dict[str, Any]) -> Optional[TelegramMessage]:
    """Parse incoming webhook data into clean message object."""
    message = data.get("message") or data.get("edited_message")
    if not message:
        return None

    user = message.get("from", {})
    chat = message.get("chat", {})
    text = (message.get("text") or "").strip()

    if not text or not text.startswith('/'):
        return None  # Only process commands for now

    return TelegramMessage(
        chat_id=chat["id"],
        user_id=user["id"],
        username=user.get("username"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        text=text
    )


@csrf_exempt
def telegram_webhook(request):
    """Handle incoming webhook POSTs from Telegram - clean and simple!"""
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        msg = parse_telegram_message(data)

        if msg:
            print(f"📥 Processing: {msg.text} from user {msg.user_id}")
            # Just handle it directly - no async complexity!
            bot.handle_message(msg)
            print(f"✅ Completed: {msg.text}")
        else:
            print("📥 Received non-command message, ignoring")

    except Exception as e:
        print(f"❌ Webhook error: {e}")

    # Always return success to Telegram quickly
    return JsonResponse({"ok": True})


# Optional: Health check endpoint
def health_check(request):
    """Simple health check for the bot."""
    return JsonResponse({
        "status": "healthy",
        "bot_token_configured": bool(TOKEN),
        "api_url": API_URL
    })
