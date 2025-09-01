import os, json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def telegram_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    update = json.loads(request.body.decode("utf-8"))
    # TODO: dispatch to handlers based on incoming message
    return JsonResponse({"ok": True})
