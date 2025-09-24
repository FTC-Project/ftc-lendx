from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, List, Optional

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


MAX_DAYS = 90


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _parse_days(value: str) -> Optional[int]:
    try:
        days = int(value)
    except ValueError:
        return None
    return days if days > 0 else None


def _valid_symbol(value: str) -> bool:
    return value.isalnum() and value.isascii()


def _extract_arguments(args: List[str]) -> Optional[dict[str, object]]:
    coin_symbol = "xrp"
    remaining = list(args)

    if remaining and not _parse_days(remaining[0]) and not _is_iso_date(remaining[0]):
        if not _valid_symbol(remaining[0]):
            return None
        coin_symbol = remaining.pop(0).lower()

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    days = 30

    if remaining:
        if len(remaining) == 1:
            token = remaining[0]
            if _is_iso_date(token):
                parsed = date.fromisoformat(token)
                start_date = parsed
                end_date = parsed
            else:
                parsed_days = _parse_days(token)
                if parsed_days is None:
                    return None
                days = min(parsed_days, MAX_DAYS)
        elif len(remaining) == 2:
            first, second = remaining
            if _is_iso_date(first) and _is_iso_date(second):
                start_date = date.fromisoformat(first)
                end_date = date.fromisoformat(second)
                if start_date > end_date:
                    return None
            else:
                return None
        else:
            return None

    return {
        "coin_symbol": coin_symbol,
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
    }


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Queue price history retrieval for asynchronous execution."""
    from ..tasks import fetch_price_history_task

    args = msg.args or []
    parsed = _extract_arguments(args)
    if parsed is None:
        bot.send_message(
            msg.chat_id,
            (
                "❌ Invalid input. Use /prices [symbol] [days] or /prices [symbol] "
                "[start-date] [end-date] (YYYY-MM-DD)."
            ),
        )
        return

    if parsed["start_date"] and parsed["end_date"]:
        from_str = parsed["start_date"].isoformat()
        to_str = parsed["end_date"].isoformat()
    else:
        from_str = None
        to_str = None

    setattr(msg, "coin_symbol", parsed["coin_symbol"])
    setattr(msg, "from_date", from_str)
    setattr(msg, "to_date", to_str)
    setattr(msg, "days", parsed["days"])

    bot.send_message(msg.chat_id, "⏳ Fetching price history…")
    fetch_price_history_task.delay(msg.__dict__)
