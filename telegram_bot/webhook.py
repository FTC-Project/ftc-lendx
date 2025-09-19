import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .bot import API_URL, TOKEN, bot
from .messages import parse_telegram_message


@csrf_exempt
def telegram_webhook(request):
    """Handle incoming webhook POSTs from Telegram."""
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        msg = parse_telegram_message(data)

        if msg:
            print(f"Processing: {msg.text} from user {msg.user_id}")
            bot.handle_message(msg)
            print(f"Completed: {msg.text}")
        else:
            print("Received non-command message, ignoring")

    except Exception as exc:  # noqa: BLE001 - ensure we never break Telegram retries
        print(f"Webhook error: {exc}")

    return JsonResponse({"ok": True})


def health_check(request):
    """Simple health check for the bot."""
    return JsonResponse({
        "status": "healthy",
        "bot_token_configured": bool(TOKEN),
        "api_url": API_URL,
    })
