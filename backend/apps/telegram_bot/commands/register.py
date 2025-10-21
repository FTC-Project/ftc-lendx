from __future__ import annotations

import mimetypes
import os
import re
from typing import Dict, Optional, Tuple

import requests
from celery import shared_task

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.flow import (
    start_flow,
    set_step,
    clear_flow,
    prev_step_of,
    mark_prev_keyboard,
    reply,
)
from backend.apps.telegram_bot.keyboards import kb_back_cancel, kb_options, kb_confirm

from backend.apps.users.models import TelegramUser
from backend.apps.kyc.models import KYCVerification, Document
from backend.apps.tokens.models import CreditTrustBalance
from backend.apps.pool.models import PoolAccount


# -------- Flow config --------
CMD = "register"

S_FIRST = "awaiting_first_name"
S_LAST = "awaiting_last_name"
S_PHONE = "awaiting_phone"
S_NATID = "awaiting_national_id"
S_ROLE = "awaiting_role"
S_ID_PHOTO = "awaiting_id_photo"
S_REVIEW = "awaiting_review"
S_CONFIRM = "awaiting_confirm"

PREV: Dict[str, Optional[str]] = {
    S_FIRST: None,
    S_LAST: S_FIRST,
    S_PHONE: S_LAST,
    S_NATID: S_PHONE,
    S_ROLE: S_NATID,
    S_ID_PHOTO: S_ROLE,
    S_REVIEW: S_ID_PHOTO,
    S_CONFIRM: S_REVIEW,
}

# For the POC, a user may be exactly one of these roles.
ROLES = [
    ("Borrower", "role:borrower"),
    ("Lender", "role:lender"),
    ("Admin", "role:admin"),
]

_re_sa_id = re.compile(r"^\d{13}$")  # SA ID: 13 digits
_re_phone = re.compile(r"^\+27\d{9}$")  # SA Phone: +27XXXXXXXXX


def prompt_for(step: str, old_value: Optional[Dict[str, any]]) -> str:
    def safe(val):
        return None if val is None or val == "None" or val == '' else val

    prompts = {
        S_FIRST: "Welcome! Can you confirm your first name?",
        S_LAST: "Thanks! Now can you confirm your last name?",
        S_PHONE: "Can you confirm your South African phone number?\nFormat: +27XXXXXXXXX",
        S_NATID: "Can you confirm your South African ID number (13 digits)?",
        S_ROLE: "Can you confirm your role (one only)?",
        S_ID_PHOTO: (
            "Please upload a clear photo of your SA ID (front).\n\n"
            "Tip: Use good lighting; the text must be readable."
        ),
        S_REVIEW: "Review your details below and press Confirm if everything looks good:",
        S_CONFIRM: "Almost done! Press Confirm to complete registration.",
    }

    if step == S_FIRST:
        val = safe(old_value.get('first_name', '') if old_value else None)
        if val:
            prompts[S_FIRST] += f"\nWe think it's: {val}. \nIf this is correct, just reply with 'yes'"
    elif step == S_LAST:
        first = safe(old_value.get('first_name', '') if old_value else None)
        prompts[S_LAST] = f"Thanks {first or ''}! Now can you confirm your last name?"
        val = safe(old_value.get('last_name', '') if old_value else None)
        if val:
            prompts[S_LAST] += f"\nWe think it's: {val}. \nIf this is correct, just reply with 'yes'"
    elif step == S_PHONE:
        val = safe(old_value.get('phone_e164', '') if old_value else None)
        if val:
            prompts[S_PHONE] += f"\nWe think it's: {val}. \nIf this is correct, just reply with 'yes'"
    elif step == S_NATID:
        val = safe(old_value.get('national_id', '') if old_value else None)
        if val:
            prompts[S_NATID] += f"\nWe think it's: {val}. \nIf this is correct, just reply with 'yes'"
    elif step == S_ROLE:
        val = safe(old_value.get('role', '') if old_value else None)
        if val:
            prompts[S_ROLE] += f"\nWe think it's: {val.capitalize()}. \nIf this is correct, press the button with the checkmark (✅) next to it or select a new role."

    return prompts[step]


def render_summary(d: dict) -> str:
    return (
        "Please confirm your details:\n"
        f"• Name: {d.get('first_name','')} {d.get('last_name','')}\n"
        f"• Phone: {d.get('phone_e164','')}\n"
        f"• SA ID: {d.get('national_id','')}\n"
        f"• Role: {d.get('role','')}\n"
        f"• ID Photo: {'✅ uploaded' if d.get('id_photo_uploaded') else '❌ missing'}\n"
    )


def role_keyboard(old_role: Optional[str]) -> dict:
    # Compose role buttons + back/cancel
    keyboard = kb_back_cancel(kb_options(ROLES)["inline_keyboard"])
    if old_role == "":
        return keyboard
    if old_role:
        # Highlight the currently selected role
        for row in keyboard["inline_keyboard"]:
            for btn in row:
                if btn.get("callback_data") == f"role:{old_role}":
                    btn["text"] = f"✅ {btn['text']}"
    return keyboard


def download_telegram_file(file_id: str) -> Tuple[bytes, str]:
    """
    Resolve a Telegram file_id to bytes + best-effort mime type.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    api_root = "https://api.telegram.org"
    api_url = f"{api_root}/bot{token}"

    # Step 1: getFile -> path
    r = requests.get(f"{api_url}/getFile", params={"file_id": file_id}, timeout=10)
    r.raise_for_status()
    file_path = r.json()["result"]["file_path"]

    # Step 2: download the file
    file_url = f"{api_root}/file/bot{token}/{file_path}"
    f = requests.get(file_url, timeout=20)
    f.raise_for_status()
    blob = f.content

    # Guess mime from extension if we can
    mime, _ = mimetypes.guess_type(file_path)
    if not mime:
        mime = "application/octet-stream"
    return blob, mime


@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="User Registration + KYC",
    permission="public",
)
class RegisterCommand(BaseCommand):
    name = CMD
    description = "User Registration + KYC"
    permission = "public"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()

        state = fsm.get(msg.chat_id)

        # Start flow
        if not state:
            user = TelegramUser.objects.filter(telegram_id=msg.user_id).first()
            if user:
                if not user.is_active:
                    clear_flow(fsm, msg.chat_id)
                    reply(
                        msg,
                        "You need to accept the Terms of Service before registering. Please use /start to accept the TOS.",
                    )
                    return
                if user.is_registered:
                    clear_flow(fsm, msg.chat_id)
                    reply(msg, "You're already registered. Use /help to see commands.")
                    return
            else:
                # No user yet, ask them to accept TOS first
                clear_flow(fsm, msg.chat_id)
                reply(
                    msg,
                    "I don't think we've met you before! \n Please use /start to begin your journey.",
                )
                return
            data = {
                "first_name": user.first_name if user else None,
                "last_name": user.last_name if user else None,
                "phone_e164": user.phone_e164 if user else None,
                "national_id": user.national_id if user else None,
                "role": user.role if user else None,
                "id_photo_uploaded": False,  # track document presence in review
            }
            start_flow(fsm, msg.chat_id, CMD, data, S_FIRST)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_FIRST, data), kb_back_cancel(), data=data)
            return

        # Guard: other command owns this chat
        if state.get("command") != CMD:
            return

        step = state.get("step")
        data = state.get("data", {}) or {}

        # --- Callbacks: cancel/back/confirm + role selection ---
        cb = getattr(msg, "callback_data", None)
        if cb:
            if cb == "flow:cancel":
                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "Registration cancelled. You can restart with /register.",
                    data=data,
                )
                return

            if cb == "flow:back":
                prev = prev_step_of(PREV, step)
                if prev is None:
                    clear_flow(fsm, msg.chat_id)
                    mark_prev_keyboard(data, msg)
                    reply(msg, "Registration cancelled.", data=data)
                    return
                set_step(fsm, msg.chat_id, CMD, prev, data)
                mark_prev_keyboard(data, msg)
                # Choose keyboard by step
                if prev == S_ROLE:
                    kb = role_keyboard(data.get("role"))
                elif prev == S_REVIEW or prev == S_CONFIRM:
                    kb = kb_confirm()
                else:
                    kb = kb_back_cancel()
                text = (
                    render_summary(data)
                    if prev in (S_REVIEW, S_CONFIRM)
                    else prompt_for(prev, data)
                )
                reply(msg, text, kb, data=data)
                return

            if cb.startswith("role:") and step == S_ROLE:
                role = cb.split("role:", 1)[1]
                print(f"Selected role: {role}")
                if role not in {"borrower", "lender", "admin"}:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "Invalid role. Please choose again.",
                        role_keyboard(data.get("role")),
                        data=data,
                    )
                    return
                # POC: User may be exactly one role; store chosen role
                data["role"] = role
                # Next: ask for ID photo upload
                set_step(fsm, msg.chat_id, CMD, S_ID_PHOTO, data)
                mark_prev_keyboard(data, msg)
                reply(msg, prompt_for(S_ID_PHOTO, data), kb_back_cancel(), data=data)
                return

            if cb == "flow:confirm" and step in (S_REVIEW, S_CONFIRM):
                # Final validations (POC: first/last/national_id, role present, id document uploaded)
                first = (data.get("first_name") or "").strip()
                last = (data.get("last_name") or "").strip()
                phone = (data.get("phone_e164") or "").strip()
                nid = (data.get("national_id") or "").strip()
                role = (data.get("role") or "").strip()
                ok = (
                    bool(first)
                    and bool(last)
                    and _re_sa_id.match(nid or "")
                    and _re_phone.match(phone or "")
                    and role in {"borrower", "lender", "admin"}
                    and data.get("id_photo_uploaded") is True
                )
                if not ok:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "Some details are missing or invalid. Please go back and fix.",
                        kb_confirm(),
                        data=data,
                    )
                    return
                # Update user info; user is guaranteed to exist at this point
                user = TelegramUser.objects.get(telegram_id=msg.user_id)
                fields = []
                if user.first_name != first:
                    user.first_name = first
                    fields.append("first_name")
                if user.last_name != last:
                    user.last_name = last
                    fields.append("last_name")
                if user.national_id != nid:
                    user.national_id = nid
                    fields.append("national_id")
                if user.phone_e164 != phone:
                    user.phone_e164 = phone
                    fields.append("phone_e164")
                if user.role != role:
                    user.role = role
                    fields.append("role")
                if not user.is_registered:
                    user.is_registered = True
                    fields.append("is_registered")
                if fields:
                    user.save(update_fields=fields)

                # Bootstrap related records (idempotent)
                PoolAccount.objects.get_or_create(user=user)
                CreditTrustBalance.objects.get_or_create(user=user)

                # POC “verification”: mark as verified if we have an ID doc on file
                kyc, _ = KYCVerification.objects.get_or_create(user=user)
                if data.get("id_photo_uploaded"):
                    if kyc.status != "verified":
                        kyc.status = "verified"
                        kyc.confidence = 0.9  # mock confidence
                        kyc.result = {
                            "checks": ["id_photo_present"],
                            "notes": "POC auto-verify",
                        }
                        kyc.save(update_fields=["status", "confidence", "result"])
                else:
                    # keep pending if somehow missing
                    if kyc.status != "pending":
                        kyc.status = "pending"
                        kyc.save(update_fields=["status"])

                # Done
                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "✅ Registration complete and KYC verified!\n\n"
                    "You can now /linkbank, /apply for a loan, or see /help for more.",
                    data=data,
                )
                return

            # Unknown callback
            mark_prev_keyboard(data, msg)
            reply(msg, "Unsupported action. Please use the buttons.", data=data)
            return

        # --- Text / Media input per-step ---
        text = (msg.text or "").strip()

        if step == S_FIRST:
            if not text:
                mark_prev_keyboard(data, msg)
                reply(
                    msg, "Please enter a valid first name or 'yes' if we have the right name on file.", kb_back_cancel(), data=data
                )
                return
            if not text.lower() == "yes":
                # Only update if they didn't confirm existing
                data["first_name"] = text
            set_step(fsm, msg.chat_id, CMD, S_LAST, data)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_LAST, data), kb_back_cancel(), data=data)
            return

        if step == S_LAST:
            if not text:
                mark_prev_keyboard(data, msg)
                reply(
                    msg, "Please enter a valid last name or 'yes' if we have the right name on file.", kb_back_cancel(), data=data
                )
                return
            if not text.lower() == "yes":
                # Only update if they didn't confirm existing
                data["last_name"] = text
            set_step(fsm, msg.chat_id, CMD, S_PHONE, data)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_PHONE, data), kb_back_cancel(), data=data)
            return
        
        if step == S_PHONE:
            is_yes = text.lower() == "yes"
            current_phone = data.get("phone_e164", "")
            phone_to_check = current_phone if is_yes else text
            if not _re_phone.match(phone_to_check or ""):
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "Phone number must be in the format +27XXXXXXXXX. Please enter a valid South African phone number or 'yes' if we have the right number on file.",
                    kb_back_cancel(),
                    data=data,
                )
                return
            if not is_yes:
                data["phone_e164"] = text
            set_step(fsm, msg.chat_id, CMD, S_NATID, data)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_NATID, data), kb_back_cancel(), data=data)
            return

        if step == S_NATID:
            # Normalize input
            is_yes = text.lower() == "yes"
            current_id = data.get("national_id", "")
            id_to_check = current_id if is_yes else text

            if not _re_sa_id.match(id_to_check or ""):
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "SA ID must be **13 digits**. Please enter a valid South African ID number (13 digits) or 'yes' if we have the right ID on file.",
                    kb_back_cancel(),
                    data=data,
                )
                return

            if not is_yes:
                data["national_id"] = text

            set_step(fsm, msg.chat_id, CMD, S_ROLE, data)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_ROLE, data), role_keyboard(data.get("role")), data=data)
            return

        if step == S_ROLE:
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "Please select a role using the buttons below.",
                role_keyboard(data.get("role")),
                data=data,
            )
            return

        if step == S_ID_PHOTO:
            # Expect a photo upload or a document with an image
            file_id = getattr(msg, "photo_file_id", None) or getattr(
                msg, "document_file_id", None
            )
            if not file_id:
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "Please upload a **photo** of your SA ID (front). You can take a new photo or attach an image file.",
                    kb_back_cancel(),
                    data=data,
                )
                return

            # Try to fetch and store the file
            try:
                blob, mime = download_telegram_file(file_id)
                # We don't have a TelegramUser yet; create a minimal placeholder for storing Document,
                # or use a temp approach: in this POC, we can upsert user here with basic info (first/last/id).
                user, _ = TelegramUser.objects.get(
                    telegram_id=msg.user_id
                )
                # Store/replace the 'id_front' doc (idempotent-ish)
                # If you want strict idempotency, you can upsert by kind:
                existing = user.documents.filter(kind="id_front").first()
                if existing:
                    existing.blob = blob
                    existing.mime_type = mime
                    existing.save(update_fields=["blob", "mime_type"])
                else:
                    Document.objects.create(
                        user=user, kind="id_front", blob=blob, mime_type=mime
                    )
                data["id_photo_uploaded"] = True

                # Next: review summary
                set_step(fsm, msg.chat_id, CMD, S_REVIEW, data)
                mark_prev_keyboard(data, msg)
                reply(msg, render_summary(data), kb_confirm(), data=data)
                return

            except Exception as e:
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    f"Could not process the uploaded file. Please try again (error: {e}).",
                    kb_back_cancel(),
                    data=data,
                )
                return

        if step == S_REVIEW:
            # Any text → re-show summary with confirm
            mark_prev_keyboard(data, msg)
            reply(msg, render_summary(data), kb_confirm(), data=data)
            return

        if step == S_CONFIRM:
            # They typed instead of tapping confirm
            mark_prev_keyboard(data, msg)
            reply(msg, render_summary(data), kb_confirm(), data=data)
            return

        # Fallback
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please /register again.")
