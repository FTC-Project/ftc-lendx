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
