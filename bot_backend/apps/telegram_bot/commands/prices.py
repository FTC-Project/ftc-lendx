from __future__ import annotations
from bot_backend.apps.botutils.price_history.coingecko import (
    CoinGeckoAPIError,
    PricePoint,
    PriceHistory,
    fetch_price_history,
)


from celery import shared_task
from bot_backend.apps.telegram_bot.commands.base import BaseCommand
from bot_backend.apps.telegram_bot.messages import TelegramMessage
from bot_backend.apps.telegram_bot.tasks import send_telegram_message_task




from datetime import date
from typing import List, Optional



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



def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _format_currency(currency: str, value: Optional[float]) -> str:
    if value is None:
        return f"{currency.upper()}: --"
    currency_prefixes = {
        "usd": "$",
        "zar": "R",
    }
    prefix = currency_prefixes.get(currency, "")
    return f"{currency.upper()}: {prefix}{value:,.4f}"


def _format_price_history_message(history: PriceHistory) -> str:
    if not history.prices:
        return "❌ No price data returned for the requested range."

    header = f"📈 {history.coin_symbol.upper()} price history"
    range_line = f"Range: {history.start.isoformat()} → {history.end.isoformat()}"

    lines: List[str] = []
    points = history.prices
    show_summary = len(points) > 14
    segments: List[List[PricePoint]] = [points]
    if show_summary:
        segments = [points[:7], points[-7:]]

    for index, segment in enumerate(segments):
        for point in segment:
            usd_text = _format_currency("usd", point.values.get("usd"))
            zar_text = _format_currency("zar", point.values.get("zar"))
            lines.append(f"• {point.date.isoformat()}: {usd_text} | {zar_text}")
        if show_summary and index == 0:
            lines.append("• …")

    change_parts: List[str] = []
    for currency in ("usd", "zar"):
        change_value = history.percent_change.get(currency)
        if change_value is not None:
            change_parts.append(f"{currency.upper()}: {change_value:+.2f}%")
    change_line = f"📊 Change: {' | '.join(change_parts)}" if change_parts else ""

    warning_line = ""
    if history.warnings:
        warning_bits = [f"{cur.upper()}: {msg}" for cur, msg in history.warnings.items()]
        warning_line = f"⚠️ {' | '.join(warning_bits)}"

    message_sections = [header, range_line, ""]
    message_sections.extend(lines)
    if change_line:
        message_sections.extend(["", change_line])
    if warning_line:
        message_sections.extend(["", warning_line])

    return "\n".join(section for section in message_sections if section).strip()





class PricesCommand(BaseCommand):
    def __init__(self):
        super().__init__(name="prices", description="Show historical price information")

    def handle(self, message: TelegramMessage) -> None:
        parsed = _extract_arguments(message.args)
        if parsed is None:
            send_telegram_message_task.delay(
                message.chat_id,
                "❌ Invalid input. Use /prices [symbol] [days] or /prices [symbol] "
                    "[start-date] [end-date] (YYYY-MM-DD)."
            )
            return

        if parsed["start_date"] and parsed["end_date"]:
            from_str = parsed["start_date"].isoformat()
            to_str = parsed["end_date"].isoformat()
        else:
            from_str = None
            to_str = None
        # Replace args with parsed values for the task
        msg = message
        setattr(msg, "coin_symbol", parsed["coin_symbol"])
        setattr(msg, "from_date", from_str)
        setattr(msg, "to_date", to_str)
        setattr(msg, "days", parsed["days"])
        send_telegram_message_task.delay(message.chat_id, "Fetching price history from CoinGecko...")
        self.task.delay(self.serialize(msg))


    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        symbol = (message_data.get("coin_symbol") or "xrp").lower()
        start = _parse_iso_date(message_data.get("from_date"))
        end = _parse_iso_date(message_data.get("to_date"))
        days_value = message_data.get("days")

        msg = TelegramMessage.from_payload(message_data)
        try:
            days = int(days_value)
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 365))

        try:
            history = fetch_price_history(symbol=symbol, start=start, end=end, days=days)
        except CoinGeckoAPIError as exc:
            print(f"Error fetching price history: {exc}")
            send_telegram_message_task.delay(msg.chat_id, f"❌ Could not fetch price data: {exc}")
            return

        if history.status != "ok":
            error_message = history.error or "Unknown error returned by CoinGecko."
            print(f"Price history error: {error_message}")
            send_telegram_message_task.delay(msg.chat_id, f"❌ Could not fetch price data: {error_message}")
            return

        send_telegram_message_task.delay(msg.chat_id, _format_price_history_message(history))
