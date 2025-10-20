import os
import sys
import json
import requests
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Manage Telegram webhook: set, get, or drop."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            dest="url",
            help="Public HTTPS endpoint for Telegram to call (e.g., https://<host>/webhook/telegram/). "
            "If omitted, will try PUBLIC_URL env + '/webhook/telegram/'.",
        )
        parser.add_argument(
            "--secret",
            dest="secret",
            help="Optional secret token to verify Telegram requests (X-Telegram-Bot-Api-Secret-Token).",
        )
        parser.add_argument(
            "--get", action="store_true", help="Get current webhook info."
        )
        parser.add_argument(
            "--drop", action="store_true", help="Delete current webhook (set to empty)."
        )

    def handle(self, *args, **options):
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set in environment.")

        base = f"https://api.telegram.org/bot{token}"

        # GET webhook info
        if options["get"]:
            r = requests.get(f"{base}/getWebhookInfo", timeout=10)
            self.stdout.write(json.dumps(r.json(), indent=2))
            return

        # DROP webhook
        if options["drop"]:
            r = requests.post(f"{base}/deleteWebhook", timeout=10)
            data = r.json()
            if not data.get("ok"):
                raise CommandError(f"deleteWebhook failed: {data}")
            self.stdout.write(self.style.SUCCESS("Webhook deleted."))
            return

        # SET webhook
        url = options["url"]
        if not url:
            public = os.getenv("PUBLIC_URL")
            if not public:
                raise CommandError("Provide --url or set PUBLIC_URL env var.")
            url = public.rstrip("/") + "/webhook/telegram/"

        payload = {"url": url}
        secret = options.get("secret")
        if secret:
            payload["secret_token"] = secret

        r = requests.post(f"{base}/setWebhook", data=payload, timeout=10)
        data = r.json()
        if not data.get("ok"):
            raise CommandError(f"setWebhook failed: {data}")

        self.stdout.write(self.style.SUCCESS(f"Webhook set to: {url}"))
        if secret:
            self.stdout.write(self.style.SUCCESS("Secret token registered."))

        # Show final state
        info = requests.get(f"{base}/getWebhookInfo", timeout=10).json()
        self.stdout.write(json.dumps(info, indent=2))
