from __future__ import annotations
from typing import Optional, Iterable, Tuple, List, Dict


def kb_back_cancel(extra_rows: Optional[List[List[Dict]]] = None) -> dict:
    rows = list(extra_rows or [])
    rows.append(
        [
            {"text": "⬅️ Back", "callback_data": "flow:back"},
            {"text": "✖️ Cancel", "callback_data": "flow:cancel"},
        ]
    )
    return {"inline_keyboard": rows}


def kb_options(pairs: Iterable[Tuple[str, str]]) -> dict:
    """
    Build a vertical list of buttons from (label, callback_data).
    Example: kb_options([("Yes","flow:yes"), ("No","flow:no")])
    """
    rows = [[{"text": label, "callback_data": data}] for label, data in pairs]
    return {"inline_keyboard": rows}


def kb_confirm() -> dict:
    return kb_back_cancel([[{"text": "✅ Confirm", "callback_data": "flow:confirm"}]])


def kb_accept_decline() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Accept", "callback_data": "flow:accept"},
                {"text": "❌ Decline", "callback_data": "flow:decline"},
            ]
        ]
    }


def kb_perms_continue(continue_callback: str) -> dict:
    """Keyboard with a 'Continue' button, and back/cancel."""
    return kb_back_cancel([[{"text": "Continue", "callback_data": continue_callback}]])


def kb_open_bank(url: str, authed_callback: str) -> dict:
    """Keyboard to open a bank URL and confirm authorisation."""
    return kb_back_cancel(
        [
            [{"text": "🌐 Open Bank Page", "url": url}],
            [{"text": "✅ I've authorised", "callback_data": authed_callback}],
        ]
    )


def kb_retry_authorise(url: str, authed_callback: str, retry_callback: str) -> dict:
    """Keyboard to retry opening a bank URL and confirm authorisation."""
    return kb_back_cancel(
        [
            [{"text": "🌐 Open Bank Page (again)", "url": url}],
            [
                {"text": "✅ I've authorised", "callback_data": authed_callback},
                {"text": "🔄 Check again", "callback_data": retry_callback},
            ],
        ]
    )


def kb_accounts(accts: List[Dict], callback_prefix: str) -> dict:
    """Keyboard to select a bank account from a list."""
    rows = []
    for a in accts:
        label = (
            f"{a.get('name','Account')} • {a.get('type','')} • {a.get('currency','')}"
        )
        rows.append(
            [{"text": label, "callback_data": f"{callback_prefix}{a.get('id')}"}]
        )
    return kb_back_cancel(rows)
