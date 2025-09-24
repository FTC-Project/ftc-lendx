"""Utilities for fetching XRP price history data from CoinGecko."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import requests

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "").strip()
DEFAULT_COIN_SYMBOL = "xrp"
DEFAULT_COIN_ID = "ripple"
SUPPORTED_CURRENCIES: Tuple[str, ...] = ("usd", "zar")
REQUEST_TIMEOUT = 10
MAX_DAYS = 365


class CoinGeckoAPIError(RuntimeError):
    """Raised when the CoinGecko API returns an error."""


@dataclass
class PricePoint:
    """Normalised price point for a single day."""

    date: date
    values: Dict[str, Optional[float]]


@dataclass
class PriceHistory:
    """Structured representation of price history data."""

    status: str
    error: Optional[str]
    coin_symbol: str
    coin_id: str
    start: date
    end: date
    prices: List[PricePoint]
    percent_change: Dict[str, Optional[float]]
    warnings: Dict[str, str]


def _get_headers() -> Dict[str, str]:
    if not COINGECKO_API_KEY:
        raise CoinGeckoAPIError("CoinGecko API key is not configured.")
    return {"x-cg-demo-api-key": COINGECKO_API_KEY}


def _request(url: str, params: Dict[str, object]) -> Dict[str, object]:
    response = requests.get(url, params=params, headers=_get_headers(), timeout=REQUEST_TIMEOUT)
    if response.status_code != 200:
        try:
            payload = response.json()
        except ValueError:
            payload = {"error": response.text}
        message = payload.get("error") or payload
        raise CoinGeckoAPIError(f"CoinGecko returned {response.status_code}: {message}")
    try:
        return response.json()
    except ValueError as exc:
        raise CoinGeckoAPIError("Invalid JSON received from CoinGecko.") from exc


def _parse_market_chart(data: Dict[str, object]) -> Iterable[Tuple[datetime, float]]:
    prices = data.get("prices", [])
    for entry in prices:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            continue
        timestamp_ms, price = entry
        try:
            dt = datetime.fromtimestamp(float(timestamp_ms) / 1000, tz=timezone.utc)
            value = float(price)
        except (TypeError, ValueError):
            continue
        yield dt, value


def _normalise_daily(prices: Iterable[Tuple[datetime, float]]) -> Dict[date, float]:
    daily: Dict[date, float] = {}
    for dt, value in sorted(prices):
        daily[dt.date()] = value  # keep the last value of the day
    return daily


def _resolve_coin_id(symbol: str) -> Tuple[str, str]:
    symbol_clean = symbol.strip().lower()
    if not symbol_clean:
        raise CoinGeckoAPIError("Coin symbol cannot be empty.")
    if symbol_clean == DEFAULT_COIN_SYMBOL:
        return DEFAULT_COIN_SYMBOL, DEFAULT_COIN_ID

    search_url = f"{COINGECKO_BASE_URL}/search"
    payload = _request(search_url, {"query": symbol_clean})
    coins = payload.get("coins") or []
    for coin in coins:
        coin_symbol = (coin.get("symbol") or "").lower()
        if coin_symbol == symbol_clean:
            coin_id = coin.get("id")
            if coin_id:
                return symbol_clean, coin_id
    raise CoinGeckoAPIError(f"Unable to find CoinGecko id for symbol '{symbol}'.")


def _date_to_datetime(value: date, *, inclusive_end: bool = False) -> datetime:
    dt = datetime.combine(value, time.min, tzinfo=timezone.utc)
    if inclusive_end:
        dt += timedelta(days=1)
    return dt


def _fetch_prices_for_currency(
    coin_id: str,
    currency: str,
    *,
    start: Optional[date] = None,
    end: Optional[date] = None,
    days: Optional[int] = None,
) -> Dict[date, float]:
    if start and end:
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart/range"
        params: Dict[str, object] = {
            "vs_currency": currency,
            "from": int(_date_to_datetime(start).timestamp()),
            "to": int(_date_to_datetime(end, inclusive_end=True).timestamp()),
        }
    else:
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": currency,
            "days": max(1, min(days or 1, MAX_DAYS)),
        }

    payload = _request(url, params)
    return _normalise_daily(_parse_market_chart(payload))


def fetch_price_history(
    *,
    symbol: str = DEFAULT_COIN_SYMBOL,
    start: Optional[date] = None,
    end: Optional[date] = None,
    days: int = 30,
) -> PriceHistory:
    if start and end and start > end:
        raise CoinGeckoAPIError("Start date must be on or before the end date.")

    days = max(1, min(days, MAX_DAYS))
    coin_symbol, coin_id = _resolve_coin_id(symbol)
    effective_start = start or (date.today() - timedelta(days=days))
    effective_end = end or date.today()

    usd_prices: Dict[date, float] = {}
    zar_prices: Dict[date, float] = {}

    errors: Dict[str, str] = {}
    for currency in SUPPORTED_CURRENCIES:
        try:
            history = _fetch_prices_for_currency(
                coin_id,
                currency,
                start=start,
                end=end,
                days=days,
            )
        except CoinGeckoAPIError as exc:
            errors[currency] = str(exc)
            history = {}
        if currency == "usd":
            usd_prices = history
        elif currency == "zar":
            zar_prices = history

    all_dates = sorted(set(usd_prices.keys()) | set(zar_prices.keys()))
    price_points: List[PricePoint] = []
    for day in all_dates:
        price_points.append(
            PricePoint(
                date=day,
                values={
                    "usd": usd_prices.get(day),
                    "zar": zar_prices.get(day),
                },
            )
        )

    def _percent_change(values: Dict[date, float]) -> Optional[float]:
        if len(values) < 2:
            return None
        sorted_items = sorted(values.items())
        first = sorted_items[0][1]
        last = sorted_items[-1][1]
        if first == 0:
            return None
        return ((last - first) / first) * 100

    change = {
        "usd": _percent_change(usd_prices),
        "zar": _percent_change(zar_prices),
    }

    if price_points:
        data_start = price_points[0].date
        data_end = price_points[-1].date
    else:
        data_start = effective_start
        data_end = effective_end

    if errors and not price_points:
        message = "; ".join(f"{cur.upper()}: {msg}" for cur, msg in errors.items())
        return PriceHistory(
            status="error",
            error=message,
            coin_symbol=coin_symbol,
            coin_id=coin_id,
            start=data_start,
            end=data_end,
            prices=[],
            percent_change=change,
            warnings=errors,
        )

    return PriceHistory(
        status="ok",
        error=None,
        coin_symbol=coin_symbol,
        coin_id=coin_id,
        start=data_start,
        end=data_end,
        prices=price_points,
        percent_change=change,
        warnings=errors,
    )
