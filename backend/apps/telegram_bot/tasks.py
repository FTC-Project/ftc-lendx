from __future__ import annotations

import os
import requests
from celery import shared_task
from dotenv import load_dotenv

# NEW: import FSMStore to persist last bot message id
from backend.apps.telegram_bot.fsm_store import FSMStore


@shared_task(queue="telegram_bot")
def send_telegram_message_task(
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
    callback_query_id: str | None = None,
    previous_message_id: int | None = None,
    previous_inline_message_id: str | None = None,
    parse_mode: str = "Markdown",
    # NEW ↓ persist the id of the message we’re sending into the chat’s FSM data
    fsm_persist_last_msg: bool = False,
) -> bool:
    """
    1) answerCallbackQuery (stop spinner) if provided
    2) editMessageReplyMarkup with empty keyboard to remove old buttons
    3) sendMessage
    4) (optional) persist result.message_id into FSM.data['last_bot_message_id']
    """
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    api_root = "https://api.telegram.org"
    api_url = f"{api_root}/bot{token}"

    # 1) stop spinner if needed
    if callback_query_id:
        try:
            r = requests.post(f"{api_url}/answerCallbackQuery",
                              json={"callback_query_id": callback_query_id},
                              timeout=5)
            if not r.ok:
                print(f"[task] Warning: answerCallbackQuery failed {r.status_code}: {r.text}")
        except requests.RequestException as e:
            print(f"[task] Warning: could not answer callback query ({e})")

    # 2) clear old inline keyboard on the original bot message
    if previous_inline_message_id or previous_message_id:
        edit_payload = {"reply_markup": {"inline_keyboard": []}}
        if previous_inline_message_id:
            edit_payload["inline_message_id"] = previous_inline_message_id
        else:
            edit_payload["chat_id"] = chat_id
            edit_payload["message_id"] = previous_message_id
        try:
            r = requests.post(f"{api_url}/editMessageReplyMarkup", json=edit_payload, timeout=5)
            if not r.ok:
                print(f"[task] Warning: editMessageReplyMarkup failed {r.status_code}: {r.text}")
        except requests.RequestException as e:
            print(f"[task] Warning: could not edit reply markup ({e})")

    # 3) send new message
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(f"{api_url}/sendMessage", json=payload, timeout=10)
        resp.raise_for_status()
        # 4) persist last bot message id into FSM (so next step can clear it)
        if fsm_persist_last_msg:
            try:
                j = resp.json()
                msg_id = j.get("result", {}).get("message_id")
                if msg_id:
                    fsm = FSMStore()
                    s = fsm.get(chat_id)
                    if s and isinstance(s.get("data"), dict):
                        data = s["data"]
                        data["last_bot_message_id"] = msg_id
                        # keep the same command/step, just update data
                        fsm.set(chat_id, s.get("command", ""), s.get("step", ""), data)
            except Exception as e:
                print(f"[task] Warning: could not persist last_bot_message_id: {e}")
        return True
    except requests.RequestException as exc:
        print(f"[task] Error sending message to {chat_id}: {exc}")
        return False
