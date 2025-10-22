from __future__ import annotations

import base64
import os
from typing import Dict, Optional, List

import requests
from celery import shared_task
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from backend.apps.banking.models import BankAccount, Consent as BankConsent, OAuthToken
from backend.apps.kyc.models import KYCVerification
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
CB_OPEN_UI = "lb:open_ui"  # Not used, but good for consistency
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
]


# ====== Text Helpers ======


def t_guard_fail(reason: str) -> str:
    return f"❌ You can't link a bank account yet.\n\n{reason}\n\nTry /register first (complete KYC), or /help."


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


# ====== AIS Sandbox API Client ======


class AISClient:
    """A client for the mock Open Banking AIS API."""

    def __init__(self):
        self.base_url = os.environ.get(
            "OPENBANK_BASE_URL", "https://open-banking-ais.onrender.com"
        )
        self.client_id = os.environ.get("CLIENT_ID", "tp_demo")
        self.client_secret = os.environ.get("CLIENT_SECRET", "s3cr3t")
        self.x_client_cert = os.environ.get("X_CLIENT_CERT", "DEMO-CLIENT-CERT")
        self.timeout = 15

    def _basic_auth_header(self) -> Dict[str, str]:
        auth_str = f"{self.client_id}:{self.client_secret}"
        basic = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {basic}"}

    def _auth_bearer_header(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _handle_error(self, response: requests.Response, prefix: str) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            detail = getattr(e.response, "text", "")
            raise RuntimeError(
                f"{prefix} failed ({e.response.status_code}): {detail}"
            ) from e

    def post_token(self) -> Dict:
        """POST /connect/mtls/token"""
        headers = self._basic_auth_header()
        headers["X-Client-Cert"] = self.x_client_cert
        body = {"grant_type": "client_credentials", "scope": "ais"}

        r = requests.post(
            f"{self.base_url}/connect/mtls/token",
            headers=headers,
            json=body,
            timeout=self.timeout,
        )
        if r.status_code == 415:  # Unsupported Media Type, fallback to form data
            r = requests.post(
                f"{self.base_url}/connect/mtls/token",
                headers=headers,
                data=body,
                timeout=self.timeout,
            )

        self._handle_error(r, "Token request")
        return r.json()

    def post_consent(self, access_token: str, permissions: List[str]) -> Dict:
        """POST /account-access-consents"""
        payload = {
            "permissions": permissions,
            "expirationDateTime": "2099-01-01T00:00:00Z",
        }
        r = requests.post(
            f"{self.base_url}/account-access-consents",
            json=payload,
            headers=self._auth_bearer_header(access_token),
            timeout=self.timeout,
        )
        self._handle_error(r, "Consent creation")
        return r.json()

    def get_consent(self, access_token: str, consent_id: str) -> Dict:
        """GET /account-access-consents/{consent_id}"""
        r = requests.get(
            f"{self.base_url}/account-access-consents/{consent_id}",
            headers=self._auth_bearer_header(access_token),
            timeout=self.timeout,
        )
        self._handle_error(r, "Get consent status")
        return r.json()

    def psu_authorize(
        self, access_token: str, consent_id: str, redirect_uri: str
    ) -> Dict:
        """POST /psu/authorize (simulates user approval)"""
        form = {"consentId": consent_id, "redirect_uri": redirect_uri}
        r = requests.post(
            f"{self.base_url}/psu/authorize",
            data=form,
            headers=self._auth_bearer_header(access_token),
            timeout=self.timeout,
        )
        self._handle_error(r, "PSU authorization simulation")
        return r.json() if r.text else {}

    def list_accounts(self, access_token: str) -> List[Dict]:
        """GET /accounts"""
        r = requests.get(
            f"{self.base_url}/accounts",
            headers=self._auth_bearer_header(access_token),
            timeout=self.timeout,
        )
        self._handle_error(r, "List accounts")
        data = r.json() or {}
        return data.get("data", []) if isinstance(data, dict) else data

    def get_psu_ui_url(self, consent_id: str, redirect_uri: str) -> str:
        """Constructs the PSU authorization UI URL."""
        return f"{self.base_url}/psu/authorize/ui?consentId={consent_id}&redirect_uri={redirect_uri}"


# ====== Persistence Helpers ======


def _save_oauth_token(user: TelegramUser, token_doc: Dict) -> OAuthToken:
    """Stores access/refresh tokens encrypted."""
    access = (token_doc.get("access_token") or "").encode("utf-8")
    refresh = (token_doc.get("refresh_token") or "").encode("utf-8")
    expires_in = int(token_doc.get("expires_in") or 3600)

    return OAuthToken.objects.update_or_create(
        user=user,
        provider="absa",
        defaults={
            "access_token_enc": encrypt_secret(access),
            "refresh_token_enc": (
                encrypt_secret(refresh)
                if refresh
                else encrypt_secret(
                    b"",
                )
            ),
            "scope": token_doc.get("scope") or "",
            "expires_at": timezone.now() + timezone.timedelta(seconds=expires_in),
        },
    )[0]


def _save_consent(user: TelegramUser, consent_doc: Dict) -> BankConsent:
    """Persists a view of the granted consent."""
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


def _update_consent_status(consent_pk: str, consent_doc: Dict):
    """Updates the status of a persisted consent record."""
    try:
        bc = BankConsent.objects.get(pk=consent_pk)
        status = consent_doc.get("Status")
        normalized = (
            "active"
            if status == "Authorised"
            else ("revoked" if status in ("Rejected", "Revoked") else "expired")
        )

        if bc.status != normalized:
            bc.status = normalized
            meta = bc.meta or {}
            meta["sandbox_status"] = status
            meta["AuthorisedAccounts"] = consent_doc.get("AuthorisedAccounts")
            bc.meta = meta
            bc.save(update_fields=["status", "meta"])
    except BankConsent.DoesNotExist:
        pass  # Non-fatal if not found


def _save_bank_account(user: TelegramUser, acct: Dict) -> BankAccount:
    """Creates a BankAccount record for the selected account."""
    ext_id = (acct.get("id") or "").encode("utf-8")
    return BankAccount.objects.create(
        user=user,
        provider="absa",
        external_account_id_enc=encrypt_secret(ext_id),
        display_name=(acct.get("name") or "Bank Account")[:128],
        currency=(acct.get("currency") or "ZAR")[:8],
    )


# ====== Step Handlers ======


def _handle_start(msg: TelegramMessage, fsm: FSMStore):
    """Guards and starts the bank linking flow."""
    try:
        user = TelegramUser.objects.get(telegram_id=msg.user_id)
        if user.role != "borrower":
            reply(msg, t_guard_fail("Only borrowers can link a bank account."))
            return
        kyc = KYCVerification.objects.get(user=user)
        if kyc.status != "verified":
            reply(
                msg,
                t_guard_fail("KYC not verified yet. Please complete /register first."),
            )
            return
    except (TelegramUser.DoesNotExist, KYCVerification.DoesNotExist):
        reply(msg, t_guard_fail("No verified profile found."))
        return

    data = {"redirect_uri": "https://example.com/redirect"}  # Mock redirect
    start_flow(fsm, msg.chat_id, CMD, data, S_PERMS)
    mark_prev_keyboard(data, msg)
    reply(msg, t_perms_intro(), kb_perms_continue(CB_PERMS_OK), data=data)


def _handle_cancel(msg: TelegramMessage, fsm: FSMStore):
    """Cancels the flow."""
    clear_flow(fsm, msg.chat_id)
    reply(msg, "Cancelled bank linking. You can try again with /linkbank.")


def _handle_back(msg: TelegramMessage, fsm: FSMStore, state: dict):
    """Handles the 'back' navigation."""
    step = state.get("step")
    data = state.get("data", {})
    prev = prev_step_of(PREV_STEP, step)

    if not prev:
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Exited. Use /linkbank to start again.")
        return

    set_step(fsm, msg.chat_id, CMD, prev, data)

    client = AISClient()
    consent_id = data.get("consent_id", "")
    redirect_uri = data.get("redirect_uri", "")
    ui_url = client.get_psu_ui_url(consent_id, redirect_uri)

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
        reply(
            msg,
            t_pick_account(),
            kb_accounts(data.get("accounts", []), CB_PICK_ACCT),
            data=data,
        )


def _handle_step_perms(msg: TelegramMessage, fsm: FSMStore, state: dict):
    """Handles the permissions step: creates token and consent."""
    data = state.get("data", {})
    if getattr(msg, "callback_data", None) != CB_PERMS_OK:
        reply(msg, t_perms_intro(), kb_perms_continue(CB_PERMS_OK), data=data)
        return

    try:
        user = TelegramUser.objects.get(telegram_id=msg.user_id)
        client = AISClient()

        token_doc = client.post_token()
        access_token = token_doc.get("access_token")
        if not access_token:
            raise RuntimeError("No access_token in token response")
        _save_oauth_token(user, token_doc)

        consent_doc = client.post_consent(access_token, DEFAULT_PERMISSIONS)
        consent_id = consent_doc.get("ConsentId")
        if not consent_id:
            raise RuntimeError("No ConsentId in consent response")

        bank_consent = _save_consent(user, consent_doc)

        data.update(
            {
                "access_token": access_token,
                "consent_id": consent_id,
                "bank_consent_pk": str(bank_consent.id),
            }
        )

        set_step(fsm, msg.chat_id, CMD, S_OPEN_UI, data)
        ui_url = client.get_psu_ui_url(consent_id, data["redirect_uri"])
        reply(msg, t_open_ui(), kb_open_bank(ui_url, CB_AUTHED), data=data)

    except Exception as e:
        reply(msg, t_error(e), kb_back_cancel(), data=data)


def _handle_step_auth(msg: TelegramMessage, fsm: FSMStore, state: dict):
    """Handles PSU authorization and polling."""
    data = state.get("data", {})
    step = state.get("step")
    cb = getattr(msg, "callback_data", None)

    client = AISClient()
    access_token = data.get("access_token")
    consent_id = data.get("consent_id")
    redirect_uri = data.get("redirect_uri")
    ui_url = client.get_psu_ui_url(consent_id, redirect_uri)

    if cb not in (CB_AUTHED, CB_RETRY_AUTH):
        # Re-render current screen if user just types something
        text, kbd = (
            (t_open_ui(), kb_open_bank(ui_url, CB_AUTHED))
            if step == S_OPEN_UI
            else (t_wait_auth(), kb_retry_authorise(ui_url, CB_AUTHED, CB_RETRY_AUTH))
        )
        reply(msg, text, kbd, data=data)
        return

    if not access_token or not consent_id:
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please /linkbank again.")
        return

    try:
        # Simulate PSU approval and check status
        client.psu_authorize(access_token, consent_id, redirect_uri)
        c_doc = client.get_consent(access_token, consent_id)
        status = c_doc.get("Status")

        _update_consent_status(data.get("bank_consent_pk"), c_doc)

        if status != "Authorised":
            set_step(fsm, msg.chat_id, CMD, S_WAIT_AUTH, data)
            reply(
                msg,
                t_wait_auth(),
                kb_retry_authorise(ui_url, CB_AUTHED, CB_RETRY_AUTH),
                data=data,
            )
            return

        # Authorised: move to account picking
        accts = client.list_accounts(access_token)
        data["accounts"] = accts
        set_step(fsm, msg.chat_id, CMD, S_PICK_ACCT, data)
        reply(msg, t_pick_account(), kb_accounts(accts, CB_PICK_ACCT), data=data)

    except Exception as e:
        set_step(fsm, msg.chat_id, CMD, S_WAIT_AUTH, data)
        reply(
            msg,
            t_auth_error(e),
            kb_retry_authorise(ui_url, CB_AUTHED, CB_RETRY_AUTH),
            data=data,
        )


def _handle_step_pick_account(msg: TelegramMessage, fsm: FSMStore, state: dict):
    """Handles the account selection step."""
    data = state.get("data", {})
    cb = getattr(msg, "callback_data", None)

    if cb and cb.startswith(CB_PICK_ACCT):
        acct_id = cb.split(CB_PICK_ACCT, 1)[1]
        acct = next(
            (a for a in data.get("accounts", []) if a.get("id") == acct_id),
            {"id": acct_id},
        )

        user = TelegramUser.objects.get(telegram_id=msg.user_id)
        _save_bank_account(user, acct)
        data["linked_account_id"] = acct_id

        set_step(fsm, msg.chat_id, CMD, S_DONE, data)
        reply(msg, t_done(), kb_back_cancel(), data=data)
        return

    # Re-show accounts if user typed something
    reply(
        msg,
        t_pick_account(),
        kb_accounts(data.get("accounts", []), CB_PICK_ACCT),
        data=data,
    )


def _handle_step_done(msg: TelegramMessage, fsm: FSMStore, state: dict):
    """Handles the final step."""
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
            _handle_start(msg, fsm)
            return

        if state.get("command") != CMD:
            return

        data = state.get("data", {}) or {}
        mark_prev_keyboard(data, msg)

        cb = getattr(msg, "callback_data", None)
        if cb == CB_FLOW_CANCEL:
            _handle_cancel(msg, fsm)
            return
        if cb == CB_FLOW_BACK:
            _handle_back(msg, fsm, state)
            return

        step = state.get("step")
        step_handlers = {
            S_PERMS: _handle_step_perms,
            S_OPEN_UI: _handle_step_auth,
            S_WAIT_AUTH: _handle_step_auth,
            S_PICK_ACCT: _handle_step_pick_account,
            S_DONE: _handle_step_done,
        }

        handler = step_handlers.get(step)
        if handler:
            handler(msg, fsm, state)
        else:
            clear_flow(fsm, msg.chat_id)
            reply(msg, "Your session has expired. Please start again with /linkbank.")
