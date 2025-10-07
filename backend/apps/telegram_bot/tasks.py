from __future__ import annotations

import os

from celery import shared_task
from dotenv import load_dotenv
import requests

@shared_task(queue="telegram_bot")
def send_telegram_message_task(chat_id: int, text: str) -> None:
    """Centralized task for sending Telegram messages."""
    print("[task] Sending message to chat_id", chat_id)
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    api_root = os.environ.get("TELEGRAM_API_ROOT", "https://api.telegram.org")
    api_url = f"{api_root}/bot{token}"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    
    try:
        response = requests.post(
            f"{api_url}/sendMessage",
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        return False