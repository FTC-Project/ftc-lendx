import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .messages import parse_telegram_message
from .bot import get_bot


@csrf_exempt
def telegram_webhook(request):
    """Process Telegram updates by enqueueing a Celery task."""
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        # Get the data.json from the request body
        data = json.loads(request.body.decode("utf-8"))
        # Parse into our message.
        msg = parse_telegram_message(data)

        if msg:
            print(f"[webhook] Received message from user {msg.user_id}")
            get_bot().handle_message(msg)
        else:
            print("[webhook] Ignoring non-command payload")

    except Exception as exc:  # never break Telegram retries
        print(f"[webhook] Error: {exc}")

    return JsonResponse({"ok": True})
