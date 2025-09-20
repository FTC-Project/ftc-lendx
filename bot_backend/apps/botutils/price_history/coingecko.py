# price_history/coingecko.py
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, List, Tuple

import httpx

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
ENV_KEY_NAME = "COINGECKO_API_KEY"
DEFAULT_TIMEOUT_SECS = 5.0 
DEFAULT_MAX_RETRIES = 3
RETRY_STATUS = {429, 500, 502, 503, 504}  # backoff-worthy statuses
MAX_RANGE_YEARS = 5 
XRP_CG_ID = "ripple"  # CoinGecko's id for XRP
DEFAULT_VS_CURRENCY = "zar" 


@dataclass
class CoinGeckoError(Exception):
    status_code: int
    error: str
    detail: Any | None = None

    def error_display(self) -> str:
        base = f"CoinGecko API error (status {self.status_code}): {self.error}"
        if self.detail:
            base += f" | detail={self.detail}"
        return base


def timezone_required(dt: datetime, name: str) -> None:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware (e.g., UTC).")


def validate_range(from_dt: datetime, to_dt: datetime) -> None:
    if to_dt <= from_dt:
        raise ValueError("to_dt must be strictly greater than from_dt.")
    # Limit range to ≤ 5 years (~ 5 * 366 days to be safe)
    max_seconds = 5 * 366 * 24 * 60 * 60
    if (to_dt - from_dt).total_seconds() > max_seconds:
        raise ValueError("Requested range must be ≤ 5 years.")


def unix(dt: datetime) -> int:
    # CoinGecko expects seconds (not ms) since epoch
    return int(dt.timestamp())


def get_cg_key() -> dict[str, str]:
    api_key = os.getenv(ENV_KEY_NAME)
    if not api_key:
        # You can choose to allow no key (public tier) by returning {}, but the brief asks for a key.
        raise EnvironmentError(
            f"{ENV_KEY_NAME} not set. Please export an API key or use .env."
        )
    return {"x-cg-pro-api-key": api_key}


async def get_http(
    client: httpx.AsyncClient, url: str, params: dict[str, Any]
) -> httpx.Response:
    delay = 0.5
    for attempt in range(1, DEFAULT_MAX_RETRIES + 1):
        try:
            resp = await client.get(url, params=params)
            if resp.status_code in RETRY_STATUS:
                # Try to parse error for context, then backoff
                if attempt < DEFAULT_MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
            if attempt < DEFAULT_MAX_RETRIES:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            # Surface the last network error
            raise httpx.HTTPError(f"Network error after {attempt} attempts: {e}") from e
    # Should not be reachable
    raise RuntimeError("Exhausted retries unexpectedly.")


async def fetch_price_hist_async(
    from_dt: datetime,
    to_dt: datetime,
    *,
    vs_currency: str = DEFAULT_VS_CURRENCY,
    coin_id: str = XRP_CG_ID,
    timeout_secs: float = DEFAULT_TIMEOUT_SECS,
) -> List[Tuple[datetime, float]]:
    
    timezone_required(from_dt, "from_dt")
    timezone_required(to_dt, "to_dt")
    validate_range(from_dt, to_dt)

    f = unix(from_dt)
    t = unix(to_dt)

    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart/range"
    params = {"vs_currency": vs_currency, "from": f, "to": t}
    headers = get_cg_key()

    async with httpx.AsyncClient(
        headers=headers, timeout=timeout_secs
    ) as client:
        resp = await get_http(client, url, params)
        if resp.status_code != 200:
            # Try to surface JSON error payload, else text
            try:
                data = resp.json()
            except ValueError:
                data = {"error": resp.text}
            error_msg = data.get("error") or data
            raise CoinGeckoError(resp.status_code, str(error_msg), detail=data)

        data = resp.json()
        # CoinGecko returns: {"prices": [[<ms>, <price>], ...], "market_caps": ..., "total_volumes": ...}
        raw_prices: Iterable[Iterable[float]] = data.get("prices", [])
        result: List[Tuple[datetime, float]] = []
        for pair in raw_prices:
            # Defensive parsing
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            ts_ms, price = pair
            # Convert ms -> seconds, return tz-aware UTC datetime
            ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
            try:
                price_val = float(price)
            except (TypeError, ValueError):
                continue
            result.append((ts, price_val))
        return result


def get_price_hist_sync(
    from_dt: datetime,
    to_dt: datetime,
    *,
    vs_currency: str = DEFAULT_VS_CURRENCY,
    coin_id: str = XRP_CG_ID,
    timeout_secs: float = DEFAULT_TIMEOUT_SECS,
) -> List[Tuple[datetime, float]]:


    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Avoid nested event loops; in async contexts, the caller should await the async fn.
        # Provide a clear error to guide correct usage.
        raise RuntimeError(
            "get_price_hist_sync called from within an active event loop. "
            "Use `await fetch_price_hist_async(...)` in async code."
        )

    return asyncio.run(
        fetch_price_hist_async(
            from_dt,
            to_dt,
            vs_currency=vs_currency,
            coin_id=coin_id,
            timeout_secs=timeout_secs,
        )
    )
