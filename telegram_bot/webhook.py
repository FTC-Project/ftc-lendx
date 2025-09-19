import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .bot import API_URL, TOKEN
from .messages import parse_telegram_message
from .tasks import handle_message_task


@csrf_exempt
def telegram_webhook(request):
    """Process Telegram updates by enqueueing a Celery task."""
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        msg = parse_telegram_message(data)

        if msg:
            print(f"[webhook] Received command '{msg.command}' from user {msg.user_id}")
            handle_message_task.delay(msg.__dict__)
        else:
            print("[webhook] Ignoring non-command payload")

    except Exception as exc:  # noqa: BLE001 - never break Telegram retries
        print(f"[webhook] Error: {exc}")

    return JsonResponse({"ok": True})


def health_check(request):
    """Simple health check for the bot."""
    return JsonResponse({
        "status": "healthy",
        "bot_token_configured": bool(TOKEN),
        "api_url": API_URL,
    })
