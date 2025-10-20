from __future__ import annotations
import re
from typing import Dict, Optional
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
from backend.apps.kyc.models import KYCVerification


# -------- Flow config --------
CMD = "register"

S_FIRST = "awaiting_first_name"
S_LAST = "awaiting_last_name"
S_PHONE = "awaiting_phone"
S_NATID = "awaiting_national_id"
S_ROLE = "awaiting_role"
S_CONFIRM = "awaiting_confirm"

PREV: Dict[str, Optional[str]] = {
    S_FIRST: None,
    S_LAST: S_FIRST,
    S_PHONE: S_LAST,
    S_NATID: S_PHONE,
    S_ROLE: S_NATID,
    S_CONFIRM: S_ROLE,
}

ROLES = [
    ("Borrower", "role:borrower"),
    ("Lender", "role:lender"),
    ("Admin", "role:admin"),
]

_re_phone = re.compile(r"^\+?[1-9]\d{6,14}$")
_re_sa_id = re.compile(r"^\d{13}$")


def prompt_for(step: str) -> str:
    return {
        S_FIRST: "Welcome! What is your **first name**?",
        S_LAST: "Thanks! Now your **last name**?",
        S_PHONE: "Please enter your **phone number** in E.164 format (e.g. `+27821234567`).",
        S_NATID: "Enter your **South African ID number** (13 digits).",
        S_ROLE: "Pick your **role**:",
        S_CONFIRM: "Review your details below and **Confirm** if correct:",
    }[step]


def render_summary(d: dict) -> str:
    return (
        "Please confirm your details:\n"
        f"• Name: {d.get('first_name','')} {d.get('last_name','')}\n"
        f"• Phone: {d.get('phone_e164','')}\n"
        f"• SA ID: {d.get('national_id','')}\n"
        f"• Role: {d.get('role','')}\n"
    )


@register(
    name=CMD, aliases=[f"/{CMD}"], description="User Registration", permission="public"
)
class RegisterCommand(BaseCommand):
    name = CMD
    description = "User Registration"
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
            if TelegramUser.objects.filter(telegram_id=msg.user_id).exists():
                clear_flow(fsm, msg.chat_id)
                reply(msg, "You're already registered. Use /help to see commands.")
                return
            data = {
                "first_name": None,
                "last_name": None,
                "phone_e164": None,
                "national_id": None,
                "role": None,
            }
            start_flow(fsm, msg.chat_id, CMD, data, S_FIRST)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_FIRST), kb_back_cancel(), data=data)
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
                kb = (
                    kb_options(ROLES)
                    if prev == S_ROLE
                    else (kb_confirm() if prev == S_CONFIRM else kb_back_cancel())
                )
                text = render_summary(data) if prev == S_CONFIRM else prompt_for(prev)
                reply(msg, text, kb, data=data)
                return

            if cb.startswith("role:") and step == S_ROLE:
                role = cb.split("role:", 1)[1]
                if role not in {"borrower", "lender", "admin"}:
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "Invalid role. Please choose again.",
                        kb_back_cancel(kb_options(ROLES)["inline_keyboard"]),
                        data=data,
                    )
                    return
                data["role"] = role
                set_step(fsm, msg.chat_id, CMD, S_CONFIRM, data)
                mark_prev_keyboard(data, msg)
                reply(msg, render_summary(data), kb_confirm(), data=data)
                return

            if cb == "flow:confirm" and step == S_CONFIRM:
                # Validate before persisting
                first = (data.get("first_name") or "").strip()
                last = (data.get("last_name") or "").strip()
                phone = (data.get("phone_e164") or "").strip()
                nid = (data.get("national_id") or "").strip()
                role = (data.get("role") or "borrower").strip()

                if (
                    not first
                    or not last
                    or not _re_phone.match(phone)
                    or not _re_sa_id.match(nid)
                ):
                    mark_prev_keyboard(data, msg)
                    reply(
                        msg,
                        "Some details are invalid. Please go back and fix.",
                        data=data,
                    )
                    return

                user, created = TelegramUser.objects.get_or_create(
                    telegram_id=msg.user_id,
                    defaults={
                        "username": msg.username,
                        "first_name": first,
                        "last_name": last,
                        "phone_e164": phone,
                        "national_id": nid,
                        "role": role,
                        "is_active": True,
                    },
                )
                if not created:
                    fields = []
                    if not user.first_name and first:
                        user.first_name = first
                        fields.append("first_name")
                    if not user.last_name and last:
                        user.last_name = last
                        fields.append("last_name")
                    if not user.phone_e164 and phone:
                        user.phone_e164 = phone
                        fields.append("phone_e164")
                    if not user.national_id and nid:
                        user.national_id = nid
                        fields.append("national_id")
                    if user.role != role:
                        user.role = role
                        fields.append("role")
                    if fields:
                        user.save(update_fields=fields)

                KYCVerification.objects.get_or_create(
                    user=user, defaults={"status": "pending"}
                )

                clear_flow(fsm, msg.chat_id)
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "✅ Registration complete! Use /kyc next or /wallet to manage funds.",
                    data=data,
                )
                return

            # Unknown callback
            mark_prev_keyboard(data, msg)
            reply(msg, "Unsupported action. Please use the buttons.", data=data)
            return

        # --- Text input per-step ---
        text = (msg.text or "").strip()

        if step == S_FIRST:
            if not text:
                mark_prev_keyboard(data, msg)
                reply(
                    msg, "Please enter a valid first name.", kb_back_cancel(), data=data
                )
                return
            data["first_name"] = text
            set_step(fsm, msg.chat_id, CMD, S_LAST, data)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_LAST), kb_back_cancel(), data=data)
            return

        if step == S_LAST:
            if not text:
                mark_prev_keyboard(data, msg)
                reply(
                    msg, "Please enter a valid last name.", kb_back_cancel(), data=data
                )
                return
            data["last_name"] = text
            set_step(fsm, msg.chat_id, CMD, S_PHONE, data)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_PHONE), kb_back_cancel(), data=data)
            return

        if step == S_PHONE:
            if not _re_phone.match(text):
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "That doesn't look like a valid phone. Use `+27821234567`.",
                    kb_back_cancel(),
                    data=data,
                )
                return
            data["phone_e164"] = text
            set_step(fsm, msg.chat_id, CMD, S_NATID, data)
            mark_prev_keyboard(data, msg)
            reply(msg, prompt_for(S_NATID), kb_back_cancel(), data=data)
            return

        if step == S_NATID:
            if not _re_sa_id.match(text):
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "SA ID must be **13 digits**. Try again.",
                    kb_back_cancel(),
                    data=data,
                )
                return
            data["national_id"] = text
            set_step(fsm, msg.chat_id, CMD, S_ROLE, data)
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                prompt_for(S_ROLE),
                kb_back_cancel(kb_options(ROLES)["inline_keyboard"]),
                data=data,
            )  # show role buttons
            return

        if step == S_ROLE:
            # nudge: must use buttons
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "Please select a role using the buttons below.",
                kb_back_cancel(kb_options(ROLES)["inline_keyboard"]),
                data=data,
            )
            return

        if step == S_CONFIRM:
            mark_prev_keyboard(data, msg)
            reply(msg, render_summary(data), kb_confirm(), data=data)
            return

        # Fallback
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please /register again.")
