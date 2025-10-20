from __future__ import annotations
from typing import Optional, Dict

from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.tasks import send_telegram_message_task


# ---------- FSM helpers ----------

def start_flow(fsm: FSMStore, chat_id: int, command: str, initial_data: dict, first_step: str) -> None:
    """Initialize a flow: set command+step+data."""
    with fsm.lock(chat_id):
        fsm.set(chat_id, command, first_step, initial_data or {})

def set_step(fsm: FSMStore, chat_id: int, command: str, step: str, data: dict) -> None:
    """Advance to a specific step with data."""
    with fsm.lock(chat_id):
        fsm.set(chat_id, command, step, data or {})

def clear_flow(fsm: FSMStore, chat_id: int) -> None:
    with fsm.lock(chat_id):
        fsm.clear(chat_id)

def prev_step_of(prev_map: Dict[str, Optional[str]], current_step: str) -> Optional[str]:
    return prev_map.get(current_step)


# ---------- UI helpers (keyboard cleanup + spinner + persist last bot msg) ----------

def mark_prev_keyboard(data: dict, msg: TelegramMessage) -> None:
    """
    Decide which previous bot message's inline keyboard to clear next:
    - if callback → clear the tapped bot message (msg.message_id)
    - else       → clear last prompt id stored in data['last_bot_message_id']
    """
    if getattr(msg, "callback_query_id", None) and getattr(msg, "message_id", None):
        data["prev_bot_message_id"] = msg.message_id
    elif data.get("last_bot_message_id"):
        data["prev_bot_message_id"] = data["last_bot_message_id"]

def reply(msg: TelegramMessage, text: str, reply_markup: dict | None = None, data: dict | None = None) -> None:
    """Send next prompt; clears previous inline keyboard; stops spinner; persists new msg_id into FSM."""
    prev_id = data.pop("prev_bot_message_id", None) if data else None
    send_telegram_message_task.delay(
        chat_id=msg.chat_id,
        text=text,
        reply_markup=reply_markup,
        callback_query_id=getattr(msg, "callback_query_id", None),
        previous_message_id=prev_id,
        fsm_persist_last_msg=True,   # writes data['last_bot_message_id'] for next turn
    )
