from __future__ import annotations

import random
from typing import Any, Dict, Iterable, List, Optional, Tuple

from celery import shared_task
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from backend.apps.banking.adapters import AISClient
from backend.apps.banking.models import BankAccount, Consent as BankConsent, OAuthToken
from backend.apps.kyc.models import KYCVerification
from backend.apps.scoring.tasks import start_scoring_pipeline
from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.flow import (
    clear_flow,
    mark_prev_keyboard,
    prev_step_of,
    reply,
    set_step,
    start_flow,
)
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.keyboards import (
    kb_accounts,
    kb_back_cancel,
    kb_open_bank,
    kb_perms_continue,
    kb_retry_authorise,
)
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.users.crypto import encrypt_secret
from backend.apps.users.models import TelegramUser

# ====== Config / Constants ======

CMD = "linkbank"

# --- Flow Steps ---
S_PERMS = "ask_permissions"
S_OPEN_UI = "open_psu_ui"
S_WAIT_AUTH = "wait_authorisation"
S_PICK_ACCT = "pick_account"
S_DONE = "completed"

# --- Callback Data ---
CB_FLOW_BACK = "flow:back"
CB_FLOW_CANCEL = "flow:cancel"
CB_PERMS_OK = "lb:perms_ok"
CB_OPEN_UI = "lb:open_ui"  # reserved
CB_AUTHED = "lb:authed"
CB_RETRY_AUTH = "lb:retry_auth"
CB_PICK_ACCT = "lb:acct:"  # e.g., lb:acct:<id>

# --- Navigation ---
PREV_STEP = {
    S_PERMS: None,
    S_OPEN_UI: S_PERMS,
    S_WAIT_AUTH: S_OPEN_UI,
    S_PICK_ACCT: S_WAIT_AUTH,
    S_DONE: S_PICK_ACCT,
}

# --- Permissions ---
DEFAULT_PERMISSIONS = [
    "ReadAccountsBasic",
    "ReadAccountsDetail",
    "ReadBalances",
    "ReadTransactionsBasic",
    "ReadTransactionsCredits",
    "ReadTransactionsDebits",
]

# ====== Text Helpers ======


def t_guard_fail(reason: str) -> str:
    return (
        "❌ You can't link a bank account yet.\n\n"
        f"{reason}\n\nTry /register first (complete KYC), or /help."
    )


def t_perms_intro() -> str:
    return (
        "🔐 *Account Information Access*\n\n"
        "We'll request a read-only consent to access:\n"
        "• Accounts (basic + detail)\n"
        "• Balances\n"
        "• Transactions (basic)\n\n"
        "_You can revoke this any time in your bank portal._"
    )


def t_open_ui() -> str:
    return (
        "✅ Consent created.\n\n"
        "Tap below to open your bank's authorisation page, sign in, and approve access."
    )


def t_wait_auth() -> str:
    return (
        "When you've completed the bank authorisation in your browser, tap *I've authorised*, "
        "or *Check again* to refresh the status."
    )


def t_pick_account() -> str:
    return "👍 Authorisation confirmed.\n\nSelect the account you want to link:"


def t_done() -> str:
    return (
        "🔗 *Bank account linked!*\n\n"
        "We can now read balances & transactions to help with affordability and underwriting.\n"
        "Next: /apply for a loan, or check /help."
    )


def t_error(e: Exception) -> str:
    return f"Could not proceed. Please try again later.\n\n_error:_ `{e}`"


def t_auth_error(e: Exception) -> str:
    return f"Could not confirm bank authorisation yet. You can retry.\n\n_error:_ `{e}`"


# ====== Persistence & Domain Helpers ======


def save_oauth_token(user: TelegramUser, token_doc: Dict) -> OAuthToken:
    """Persist encrypted OAuth tokens with expiry & scope."""
    access = token_doc.get("access_token") or ""
    refresh = token_doc.get("refresh_token") or ""
    expires_in = int(token_doc.get("expires_in") or 3600)

    return OAuthToken.objects.update_or_create(
        user=user,
        provider="absa",
        defaults={
            "access_token_enc": encrypt_secret(access),
            "refresh_token_enc": encrypt_secret(refresh if refresh else b""),
            "scope": token_doc.get("scope") or "",
            "expires_at": timezone.now() + timezone.timedelta(seconds=expires_in),
        },
    )[0]


def save_consent(user: TelegramUser, consent_doc: Dict) -> BankConsent:
    """Persist a normalized view of the granted consent."""
    status = consent_doc.get("Status")
    normalized_status = "active" if status == "Authorised" else "pending"
    return BankConsent.objects.create(
        user=user,
        permissions=consent_doc.get("Permissions") or [],
        granted_at=parse_datetime(consent_doc.get("CreationDateTime"))
        or timezone.now(),
        expires_at=parse_datetime(consent_doc.get("ExpirationDateTime"))
        or (timezone.now() + timezone.timedelta(days=90)),
        status=normalized_status,
        meta={
            "provider": "absa",
            "sandbox_status": status,
            "ConsentId": consent_doc.get("ConsentId"),
        },
    )


def update_consent_status(consent_pk: str, consent_doc: Dict) -> None:
    """Update persisted consent status & metadata (best effort)."""
    try:
        bc = BankConsent.objects.get(pk=consent_pk)
    except BankConsent.DoesNotExist:
        return
    status = consent_doc.get("Status")
    normalized = (
        "active"
        if status == "Authorised"
        else ("revoked" if status in ("Rejected", "Revoked") else "expired")
    )
    if bc.status != normalized:
        meta = bc.meta or {}
        meta["sandbox_status"] = status
        meta["AuthorisedAccounts"] = consent_doc.get("AuthorisedAccounts")
        bc.status = normalized
        bc.meta = meta
        bc.save(update_fields=["status", "meta"])


def save_bank_account(user: TelegramUser, acct: Dict) -> BankAccount:
    """Create a BankAccount record for the selected account."""
    ext_id = acct.get("id") or ""
    return BankAccount.objects.create(
        user=user,
        provider="absa",
        external_account_id_enc=encrypt_secret(ext_id),
        display_name=(acct.get("name") or "Bank Account")[:128],
        currency=(acct.get("currency") or "ZAR")[:8],
    )


def normalize_accounts(payload: Any) -> List[Dict]:
    """Accepts either {data:[...]} or [...] and returns a list of account dicts."""
    if isinstance(payload, dict):
        payload = payload.get("data", []) or []
    if isinstance(payload, list):
        return [a for a in payload if isinstance(a, dict)]
    return []


def get_user_guarded(telegram_id: int) -> Tuple[Optional[TelegramUser], Optional[str]]:
    """Fetch user and ensure borrower role + verified KYC; returns (user, error_msg)."""
    try:
        user = TelegramUser.objects.get(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return None, t_guard_fail("No verified profile found.")
    if user.role != "borrower":
        return None, t_guard_fail("Only borrowers can link a bank account.")
    try:
        kyc = KYCVerification.objects.get(user=user)
    except KYCVerification.DoesNotExist:
        return None, t_guard_fail("No verified profile found.")
    if kyc.status != "verified":
        return None, t_guard_fail(
            "KYC not verified yet. Please complete /register first."
        )
    return user, None


def make_ui_url(client: AISClient, data: Dict) -> str:
    """Build PSU UI URL from stored flow data."""
    return client.get_psu_ui_url(
        data.get("consent_id", ""),
        data.get("psu_id", ""),
        data.get("redirect_uri", ""),
    )


def pick_account_from_callback(cb: str) -> Optional[str]:
    """Extract account id from a callback like 'lb:acct:<id>'."""
    if cb and cb.startswith(CB_PICK_ACCT):
        return cb.split(CB_PICK_ACCT, 1)[1]
    return None


# ====== Step Handlers ======


def handle_start(msg: TelegramMessage, fsm: FSMStore) -> None:
    """Guards and starts the bank linking flow."""
    user, err = get_user_guarded(msg.user_id)
    if err:
        reply(msg, err)
        return

    data = {"redirect_uri": "https://example.com/redirect"}  # Mock redirect
    start_flow(fsm, msg.chat_id, CMD, data, S_PERMS)
    mark_prev_keyboard(data, msg)
    reply(msg, t_perms_intro(), kb_perms_continue(CB_PERMS_OK), data=data)


def handle_cancel(msg: TelegramMessage, fsm: FSMStore) -> None:
    clear_flow(fsm, msg.chat_id)
    reply(msg, "Cancelled bank linking. You can try again with /linkbank.")


def handle_back(msg: TelegramMessage, fsm: FSMStore, state: dict) -> None:
    step = state.get("step")
    data = state.get("data", {})
    prev = prev_step_of(PREV_STEP, step)

    if not prev:
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Exited. Use /linkbank to start again.")
        return

    set_step(fsm, msg.chat_id, CMD, prev, data)

    client = AISClient()
    ui_url = make_ui_url(client, data)

    if prev == S_PERMS:
        reply(msg, t_perms_intro(), kb_perms_continue(CB_PERMS_OK), data=data)
    elif prev == S_OPEN_UI:
        reply(msg, t_open_ui(), kb_open_bank(ui_url, CB_AUTHED), data=data)
    elif prev == S_WAIT_AUTH:
        reply(
            msg,
            t_wait_auth(),
            kb_retry_authorise(ui_url, CB_AUTHED, CB_RETRY_AUTH),
            data=data,
        )
    elif prev == S_PICK_ACCT:
        accounts = normalize_accounts(data.get("accounts", []))
        reply(msg, t_pick_account(), kb_accounts(accounts, CB_PICK_ACCT), data=data)


def handle_permissions(msg: TelegramMessage, fsm: FSMStore, state: dict) -> None:
    """Create initial client token and a consent, then push user to PSU UI."""
    data = state.get("data", {})
    if getattr(msg, "callback_data", None) != CB_PERMS_OK:
        reply(msg, t_perms_intro(), kb_perms_continue(CB_PERMS_OK), data=data)
        return

    try:
        user = TelegramUser.objects.get(telegram_id=msg.user_id)
        client = AISClient()

        # 1) Client-credentials token (no consent)
        token_doc = client.post_token()
        access_token = token_doc.get("access_token")
        if not access_token:
            raise RuntimeError("No access_token in token response")
        save_oauth_token(user, token_doc)

        # 2) Create consent
        consent_doc = client.post_consent(access_token, DEFAULT_PERMISSIONS)
        consent_id = consent_doc.get("ConsentId")
        if not consent_id:
            raise RuntimeError("No ConsentId in consent response")

        bank_consent = save_consent(user, consent_doc)
        psu_id = random.choice(["mk1", "sm1", "ad1", "an1"])  # FinHub sample PSUs

        data.update(
            {
                "access_token": access_token,
                "consent_id": consent_id,
                "bank_consent_pk": str(bank_consent.id),
                "psu_id": psu_id,
            }
        )

        set_step(fsm, msg.chat_id, CMD, S_OPEN_UI, data)
        ui_url = make_ui_url(client, data)
        reply(msg, t_open_ui(), kb_open_bank(ui_url, CB_AUTHED), data=data)

    except Exception as e:
        reply(msg, t_error(e), kb_back_cancel(), data=data)


def handle_authorisation(msg: TelegramMessage, fsm: FSMStore, state: dict) -> None:
    """Confirm PSU authorisation, mint consent-scoped token, and list accounts."""
    data = state.get("data", {})
    step = state.get("step")
    cb = getattr(msg, "callback_data", None)

    client = AISClient()
    ui_url = make_ui_url(client, data)

    # If user typed text instead of pressing a button, re-render current step UI
    if cb not in (CB_AUTHED, CB_RETRY_AUTH):
        text, kbd = (
            (t_open_ui(), kb_open_bank(ui_url, CB_AUTHED))
            if step == S_OPEN_UI
            else (t_wait_auth(), kb_retry_authorise(ui_url, CB_AUTHED, CB_RETRY_AUTH))
        )
        reply(msg, text, kbd, data=data)
        return

    access_token = data.get("access_token")
    consent_id = data.get("consent_id")
    if not access_token or not consent_id:
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please /linkbank again.")
        return

    try:
        # 1) Poll consent status
        c_doc = client.get_consent(access_token, consent_id)
        status = c_doc.get("Status")
        update_consent_status(data.get("bank_consent_pk"), c_doc)

        if status != "Authorised":
            set_step(fsm, msg.chat_id, CMD, S_WAIT_AUTH, data)
            reply(
                msg,
                t_wait_auth(),
                kb_retry_authorise(ui_url, CB_AUTHED, CB_RETRY_AUTH),
                data=data,
            )
            return

        # 2) Mint consent-bound token
        token_doc = client.post_token(consent_id)
        access_token = token_doc.get("access_token")
        if not access_token:
            raise RuntimeError("No access_token in token response after consent")
        save_oauth_token(TelegramUser.objects.get(telegram_id=msg.user_id), token_doc)
        data["access_token"] = access_token

        # 3) List accounts, normalize, then prompt selection
        accts_doc = client.list_accounts(access_token)
        accounts = normalize_accounts(accts_doc)
        data["accounts"] = accounts

        set_step(fsm, msg.chat_id, CMD, S_PICK_ACCT, data)
        reply(msg, t_pick_account(), kb_accounts(accounts, CB_PICK_ACCT), data=data)

    except Exception as e:
        set_step(fsm, msg.chat_id, CMD, S_WAIT_AUTH, data)
        reply(
            msg,
            t_auth_error(e),
            kb_retry_authorise(ui_url, CB_AUTHED, CB_RETRY_AUTH),
            data=data,
        )


def handle_pick_account(msg: TelegramMessage, fsm: FSMStore, state: dict) -> None:
    """Persist selected account and kick off scoring."""
    data = state.get("data", {}) or {}
    cb = getattr(msg, "callback_data", None)

    accounts = normalize_accounts(data.get("accounts", []))
    acct_id = pick_account_from_callback(cb)

    if acct_id:
        acct = next((a for a in accounts if a.get("id") == acct_id), None) or {
            "id": acct_id,
            "name": "Bank Account",
            "currency": "ZAR",
        }

        user = TelegramUser.objects.get(telegram_id=msg.user_id)
        bank_account = save_bank_account(user, acct)
        data["linked_account_id"] = acct_id

        start_scoring_pipeline.delay(user.id, bank_account.id)

        set_step(fsm, msg.chat_id, CMD, S_DONE, data)
        reply(msg, t_done(), data=data)
        return

    # Re-render accounts if user typed text
    reply(msg, t_pick_account(), kb_accounts(accounts, CB_PICK_ACCT), data=data)


def handle_done(msg: TelegramMessage, fsm: FSMStore, state: dict) -> None:
    clear_flow(fsm, msg.chat_id)
    reply(msg, "All set. Use /apply to request a loan, or /help.")


# ====== Command ======


@register(
    name=CMD,
    aliases=["/linkbank"],
    description="Link your bank account (AIS OAuth - mocked)",
    permission="public",
)
class LinkBankCommand(BaseCommand):
    name = CMD
    description = "Link your bank account (AIS OAuth - mocked)"
    permission = "public"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(msg.chat_id)

        if not state:
            handle_start(msg, fsm)
            return

        if state.get("command") != CMD:
            return

        data = state.get("data", {}) or {}
        mark_prev_keyboard(data, msg)

        cb = getattr(msg, "callback_data", None)
        if cb == CB_FLOW_CANCEL:
            handle_cancel(msg, fsm)
            return
        if cb == CB_FLOW_BACK:
            handle_back(msg, fsm, state)
            return

        step = state.get("step")
        step_handlers = {
            S_PERMS: handle_permissions,
            S_OPEN_UI: handle_authorisation,
            S_WAIT_AUTH: handle_authorisation,
            S_PICK_ACCT: handle_pick_account,
            S_DONE: handle_done,
        }

        handler = step_handlers.get(step)
        if handler:
            handler(msg, fsm, state)
        else:
            clear_flow(fsm, msg.chat_id)
            reply(msg, "Your session has expired. Please start again with /linkbank.")
