import os
import json
import requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

def send_message(chat_id: int, text: str):
    """Send a simple text message via Telegram Bot API."""
    try:
        requests.post(
            f"{API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5,
        )
    except Exception as e:
        # For dev: log or just ignore to keep webhook resilient
        print("Error sending message:", e)

@csrf_exempt
def telegram_webhook(request):
    """Handle incoming webhook POSTs from Telegram."""
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponse(status=400)

    message = data.get("message") or data.get("edited_message")
    if not message:
        return JsonResponse({"ok": True})  # Nothing to process

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    # --- Command routing ---
    if text.startswith("/start"):
        send_message(chat_id, "Welcome to the XRPL bot! Try /help")
    elif text.startswith("/help"):
        send_message(chat_id, "Commands: /start, /help, /balance, /send <user> <amount>")
    elif text.startswith("/balance"):
        # TODO: hook into XRPL wallet logic later
        send_message(chat_id, "Your balance is 0 XRP (XRPL integration coming soon).")
    else:
        send_message(chat_id, "Unknown command. Try /help")

    return JsonResponse({"ok": True})
