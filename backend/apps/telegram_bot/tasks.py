from __future__ import annotations

import os
import requests
from celery import shared_task
from dotenv import load_dotenv
from typing import Optional

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
    fsm_persist_last_msg: bool = False,
) -> bool:
    """
    1) answerCallbackQuery (stop spinner) if provided
    2) editMessageReplyMarkup with empty keyboard to remove old buttons
    3) sendMessage
    4) (optional) persist result.message_id into FSM.data['last_bot_message_id'] atomically
    """
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    api_root = "https://api.telegram.org"
    api_url = f"{api_root}/bot{token}"

    # 1) stop spinner if needed
    if callback_query_id:
        try:
            r = requests.post(
                f"{api_url}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id},
                timeout=5,
            )
            if not r.ok:
                print(
                    f"[task] Warning: answerCallbackQuery failed {r.status_code}: {r.text}"
                )
        except requests.RequestException as e:
            print(f"[task] Warning: could not answer callback query ({e})")

    # 2) clear old inline keyboard
    if previous_inline_message_id or previous_message_id:
        edit_payload = {"reply_markup": {"inline_keyboard": []}}
        if previous_inline_message_id:
            edit_payload["inline_message_id"] = previous_inline_message_id
        else:
            edit_payload["chat_id"] = chat_id
            edit_payload["message_id"] = previous_message_id
        try:
            r = requests.post(
                f"{api_url}/editMessageReplyMarkup", json=edit_payload, timeout=5
            )
            if not r.ok:
                print(
                    f"[task] Warning: editMessageReplyMarkup failed {r.status_code}: {r.text}"
                )
        except requests.RequestException as e:
            print(f"[task] Warning: could not edit reply markup ({e})")

    # 3) send new message
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(f"{api_url}/sendMessage", json=payload, timeout=10)
        resp.raise_for_status()

        # 4) persist last bot message id into FSM.data atomically
        if fsm_persist_last_msg:
            try:
                j = resp.json()
                msg_id = j.get("result", {}).get("message_id")
                if msg_id:
                    fsm = FSMStore()
                    fsm.update_data(chat_id, {"last_bot_message_id": msg_id})
            except Exception as e:
                print(f"[task] Warning: could not persist last_bot_message_id: {e}")

        return True
    except requests.RequestException as exc:
        print(f"[task] Error sending message to {chat_id}: {exc}")
        return False


@shared_task(queue="telegram_bot")
def check_permission_and_dispatch_task(
    message_data: dict,
    command_name: str,
    permission_level: str,
) -> None:
    """
    Non-blocking permission check that dispatches to command if authorized.

    This task:
    1. Checks if user has required permission (can query DB without blocking bot)
    2. If authorized, kicks off the command's task
    3. If not authorized, sends error message to user
    """
    from backend.apps.telegram_bot.messages import TelegramMessage
    from backend.apps.telegram_bot.registry import get_command_meta

    msg = TelegramMessage.from_payload(message_data)

    # Check permission
    has_permission = _check_user_permission(msg.user_id, permission_level)

    if not has_permission:
        # Send unauthorized message
        error_msg = _get_permission_error_message(permission_level)
        send_telegram_message_task.delay(msg.chat_id, error_msg)
        print(
            f"[task] User {msg.user_id} not authorized for {command_name} (requires {permission_level})"
        )
        return

    # User is authorized - get command and dispatch
    meta = get_command_meta(command_name)
    if not meta:
        print(f"[task] Unknown command '{command_name}' in dispatch")
        return

    # Instantiate command and get its task
    command_instance = meta.cls()
    if hasattr(command_instance, "task") and command_instance.task:
        # Dispatch to command's task
        command_instance.task.delay(message_data)
    else:
        print(f"[task] Command '{command_name}' has no task method")


def _check_user_permission(user_id: int, permission_level: str) -> bool:
    """
    Check if user has the required permission level.
    This runs in a Celery worker, so DB queries are non-blocking.
    """
    if permission_level == "public":
        return True

    # Import here to avoid circular imports
    from backend.apps.users.models import TelegramUser
    from backend.apps.kyc.models import KYCVerification

    try:
        user = TelegramUser.objects.filter(telegram_id=user_id).first()

        if not user:
            return False

        # Must be active (accepted TOS)
        if not user.is_active:
            return False

        if permission_level == "user":
            # Just needs to be an active user
            return True

        if permission_level == "registered":
            # Must have completed registration
            return user.is_registered

        if permission_level == "verified":
            # Must have verified KYC
            kyc = KYCVerification.objects.filter(user=user).first()
            return kyc and kyc.status == "verified"

        if permission_level == "verified_borrower":
            # Must be verified AND a borrower
            if user.role != "borrower":
                return False
            kyc = KYCVerification.objects.filter(user=user).first()
            return kyc and kyc.status == "verified" and user.is_registered

        if permission_level == "verified_lender":
            # Must be verified AND a lender
            if user.role != "lender":
                return False
            kyc = KYCVerification.objects.filter(user=user).first()
            return kyc and kyc.status == "verified" and user.is_registered

        if permission_level == "borrower":
            # Must be registered borrower
            return user.is_registered and user.role == "borrower"

        if permission_level == "lender":
            # Must be registered lender
            return user.is_registered and user.role == "lender"

        if permission_level == "admin":
            # Must be admin
            return user.is_registered and user.role == "admin"

        # Unknown permission level - deny by default
        print(f"[task] Unknown permission level: {permission_level}")
        return False

    except Exception as e:
        print(f"[task] Error checking permission for user {user_id}: {e}")
        return False


def _get_permission_error_message(permission_level: str) -> str:
    """Get appropriate error message for permission denial."""
    messages = {
        "user": "⛔ You need to accept the Terms of Service first. Use /start to get started.",
        "registered": "⛔ You need to complete registration first. Use /register to get started.",
        "verified": "⛔ You need to complete KYC verification first. Use /register to get started.",
        "verified_borrower": "⛔ This command is only available to verified borrowers. Please complete registration and KYC verification.",
        "verified_lender": "⛔ This command is only available to verified lenders. Please complete registration and KYC verification.",
        "borrower": "⛔ This command is only available to borrowers.",
        "lender": "⛔ This command is only available to lenders.",
        "admin": "⛔ This command is only available to administrators.",
    }
    return messages.get(
        permission_level, "⛔ You don't have permission to use this command."
    )
