from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Iterable, Optional

import pandas as pd
from celery import shared_task
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from backend.apps.audit.models import DataAccessLog
from backend.apps.banking.adapters import AISClient
from backend.apps.banking.models import (
    BankAccount,
    BankTransaction,
    Consent,
    OAuthToken,
)
from backend.apps.scoring.credit_scoring import create_feature_vector, import_scorecard
from backend.apps.scoring.limit import calculate_credit_limit
from backend.apps.scoring.models import (
    AffordabilitySnapshot,
)
from backend.apps.tokens.models import CreditTrustBalance
from backend.apps.users.crypto import decrypt_secret, encrypt_secret
from backend.apps.users.models import TelegramUser

import logging

logger = logging.getLogger(__name__)

# Max token balance to earn highest score.
TOKEN_MAX = 100000
# Weight of the trust score in the combined score.
SCORE_WEIGHT = 0.6
# Weight of the token score in the combined score.
TOKEN_WEIGHT = 0.4
# Platinum is 90-100 combined score
# Gold is 75 to 89 combined score
# Silver is 45 - 74
# Bronze is 0 - 44
SCORE_TIERS = [
    ("PLATINUM", 90, 100),
    ("GOLD", 75, 89),
    ("SILVER", 45, 74),
    ("BRONZE", 0, 44),
]


# ---------------------------
# Helpers
# ---------------------------

SCORE_TIERS = [
    ("PLATINUM", 90, 100),
    ("GOLD", 75, 89),
    ("SILVER", 45, 74),
    ("BRONZE", 0, 44),
]


# ---------------------------
# Helpers
# ---------------------------


def _get_score_tier(combined_score: float) -> str:
    """
    Determines the tier (e.g., 'PLATINUM', 'GOLD') based on the combined score.

    :param combined_score: The calculated score (C) from 0 to 100.
    :return: The tier name (str) corresponding to the score.
    """
    for tier_name, lower_bound, upper_bound in SCORE_TIERS:
        if lower_bound <= combined_score <= upper_bound:
            return tier_name

    return "BRONZE"


def _refresh_oauth_token(
    oauth_token: OAuthToken, client: AISClient, consent_id: Optional[str] = None
) -> str:
    """
    Refresh an expired OAuth token and update the database.
    Returns the new access token.
    """
    refresh_token = decrypt_secret(oauth_token.refresh_token_enc)
    if not refresh_token:
        raise ValueError("No refresh token available for token rotation")

    token_doc = client.refresh_token(refresh_token, consent_id)

    # Update the stored token
    access_token = token_doc.get("access_token")
    new_refresh_token = token_doc.get(
        "refresh_token", refresh_token
    )  # Some APIs return new refresh token
    expires_in = int(token_doc.get("expires_in", 3600))

    oauth_token.access_token_enc = encrypt_secret(access_token)
    oauth_token.refresh_token_enc = encrypt_secret(new_refresh_token)
    oauth_token.scope = token_doc.get("scope", oauth_token.scope)
    oauth_token.expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
    oauth_token.save()

    return access_token


def _to_py(obj: Any) -> Any:
    """
    If `obj` is a JSON string, parse to Python. Otherwise, return as-is.
    """
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except json.JSONDecodeError:
            raise ValueError(
                "Expected JSON string for transactions payload, got invalid JSON."
            )
    return obj


def _tx_list_from_payload(payload: Any) -> list[dict]:
    """
    Accepts either:
      - {"data": [...], "next_cursor": "..."} shape
      - Bare list [...]
    Returns the list of transactions, or raises if not found.
    """
    payload = _to_py(payload)
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        # Some APIs may return an empty page with no "data"
        if data is None:
            return []
        logger.error(f"Transactions payload 'data' key is not a list: {data}")
        raise ValueError("Transactions payload 'data' key is not a list.")
    if isinstance(payload, list):
        return payload
    logger.error(f"Transactions payload is neither a dict nor a list: {payload}")
    raise ValueError("Transactions payload is neither a dict nor a list.")


def _next_cursor_from_payload(payload: Any) -> Optional[str]:
    """
    Extract 'next_cursor' from wrapped payloads; returns None if not present.
    """
    payload = _to_py(payload)
    if isinstance(payload, dict):
        nxt = payload.get("next_cursor")
        return str(nxt) if nxt is not None else None
    return None


def normalize_tx(tx: dict) -> dict:
    """
    Map external fields into the internal keys your persistence logic expects.
    Supports two shapes:
      A) Already-normalized: has 'transactionId', 'postingDateTime', etc.
      B) ABSA-like (your sample): 'id', 'booking_date', 'description', 'merchant', 'amount', 'currency'
    """
    if "transactionId" in tx:
        # Already normalized; ensure strings and presence of expected keys
        return {
            "transactionId": str(tx.get("transactionId")),
            "postingDateTime": tx.get("postingDateTime"),
            "transactionInformation": tx.get("transactionInformation"),
            "amount": str(tx.get("amount")),
            "merchantDetails": tx.get("merchantDetails") or {},
            "currency": tx.get("currency"),
        }

    # Fallback mapping for the provided payload
    return {
        "transactionId": str(tx.get("id")),
        "postingDateTime": tx.get("booking_date"),  # e.g., '2025-08-20T16:35:00'
        "transactionInformation": tx.get("description") or tx.get("merchant"),
        "amount": str(tx.get("amount")),  # keep as string; convert later to Decimal
        "merchantDetails": {"merchantName": tx.get("merchant")},
        "currency": tx.get("currency"),
    }


def _parse_posted_at(value: Optional[str]) -> Optional[timezone.datetime]:
    """
    Parse ISO string to timezone-aware datetime (using the current TZ) if possible.
    """
    if not value:
        return None
    dt = parse_datetime(value)
    if not dt:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _persist_transactions(
    bank_account: BankAccount, normalized_txs: Iterable[dict]
) -> int:
    """
    Upsert normalized transactions into BankTransaction. Returns count persisted.
    """
    count = 0
    for ntx in normalized_txs:
        posted_at = _parse_posted_at(ntx.get("postingDateTime"))
        amt = float(str(ntx.get("amount") or "0"))
        tx_type = "credit" if amt > 0 else "debit"
        BankTransaction.objects.update_or_create(
            id=ntx.get("transactionId"),
            defaults={
                "account": bank_account,
                "posted_at": posted_at,
                "description": ntx.get("transactionInformation"),
                "amount": amt,
                "tx_type": tx_type,
                "category": (ntx.get("merchantDetails") or {}).get(
                    "merchantCategoryCode"
                ),
                "raw": ntx,
            },
        )
        count += 1
    return count


def _fetch_all_transactions(
    client: AISClient,
    access_token: str,
    from_date: Optional[str],
    to_date: Optional[str],
    page_limit: Optional[int] = None,
    oauth_token: Optional[OAuthToken] = None,
    consent_id: Optional[str] = None,
) -> tuple[list[dict], str]:
    """
    Robustly fetch *all* transactions, following pagination by 'next_cursor' if present.
    Returns the concatenated list in the *external* shape (not normalized)
    and the potentially refreshed access token.

    If a 401 error occurs and oauth_token is provided, attempts to refresh the token once.
    """
    all_txs: list[dict] = []
    after: Optional[str] = None
    current_token = access_token

    while True:
        try:
            page = client.list_transactions_all(
                access_token=current_token,
                from_date=from_date,
                to_date=to_date,
                limit=page_limit,
                after=after,
            )
            txs = _tx_list_from_payload(page)
            all_txs.extend(txs)

            nxt = _next_cursor_from_payload(page)
            if not nxt:
                break
            after = nxt  # follow cursor
        except RuntimeError as e:
            logger.error(f"Error fetching transactions: {e}")
            # Check if it's a 401 error
            if "401" in str(e) and oauth_token is not None:
                logger.info(f"Refreshing OAuth token for user: {oauth_token.user.id}")
                # Try to refresh the token once
                current_token = _refresh_oauth_token(oauth_token, client, consent_id)
                # Retry the request with the new token
                page = client.list_transactions_all(
                    access_token=current_token,
                    from_date=from_date,
                    to_date=to_date,
                    limit=page_limit,
                    after=after,
                )
                txs = _tx_list_from_payload(page)
                all_txs.extend(txs)

                nxt = _next_cursor_from_payload(page)
                if not nxt:
                    break
                after = nxt
            else:
                logger.error(f"No next cursor found: {nxt}")
                # Re-raise if not a 401 or no oauth_token provided
                raise

    return all_txs, current_token


# ---------------------------
# Task
# ---------------------------


@shared_task(queue="scoring")
def start_scoring_pipeline(user_id: int):
    """
    Starts the credit scoring and affordability calculation pipeline.
    This version:
      - Fetches ALL transactions (handles wrapped payloads + pagination)
      - Normalizes + persists safely (Decimal, TZ-aware dates)
      - Logs reads/writes
      - Computes trust score, token tier, credit limit
      - Handles empty dataframes gracefully
    """
    try:
        user = TelegramUser.objects.get(id=user_id)
        # Select the most recently added bank account for scoring
        bank_account = BankAccount.objects.filter(
            user=user
        ).order_by('-created_at').first()

        if not bank_account:
            logger.error(f"No valid bank account found for user: {user_id}")
            raise ValueError("No valid bank account found for user.")

        # 1) OAuth & Client
        oauth_token = OAuthToken.objects.get(user=user)
        if not oauth_token or not oauth_token.access_token_enc:
            logger.error(f"No valid OAuth token found for user: {user_id}")
            raise ValueError("No valid OAuth token found for user.")
        access_token = decrypt_secret(oauth_token.access_token_enc)
        client = AISClient()
        # Check if our token is expired
        if oauth_token.expires_at < timezone.now():
            logger.info(f"OAuth token expired for user: {user_id}")
            # Refresh the token
            # First obtain the consent id from the consent object meta ConsentId
            consent_id = Consent.objects.filter(user=user).first().meta.get("ConsentId")
            access_token = _refresh_oauth_token(oauth_token, client, consent_id)
            oauth_token.access_token_enc = encrypt_secret(access_token)
            oauth_token.save()

        # 2) Fetch ALL transactions (with pagination if provided by API)
        # Passing oauth_token enables automatic token refresh on 401 errors
        ext_txs, refreshed_token = _fetch_all_transactions(
            client=client,
            access_token=access_token,
            from_date="1900-01-01",
            to_date="2100-12-31",
            page_limit=None,  # or set e.g. 500 if backend enforces a maximum
            oauth_token=oauth_token,
            consent_id=None,  # Add consent_id if needed
        )

        # 3) Normalize + persist
        normalized_txs = [normalize_tx(tx) for tx in ext_txs]
        persisted_count = _persist_transactions(bank_account, normalized_txs)

        DataAccessLog.objects.create(
            user=user,
            actor="system",
            resource="banking.transactions",
            action="write",
            context={"count": persisted_count, "bank_account_id": bank_account.id},
        )

        # 4) Prepare data for scoring
        # Use transactions from the selected bank account only
        user_transactions = BankTransaction.objects.filter(account=bank_account).values()
        df = pd.DataFrame(list(user_transactions))

        DataAccessLog.objects.create(
            user=user,
            actor="system",
            resource="banking.transactions",
            action="read",
            context={"purpose": "credit_scoring"},
        )

        # Guard: empty datasets should stop the pipeline
        if df.empty:
            logger.error(f"No transactions found for user: {user_id}")
            raise ValueError("No transactions found for user.")

        # Ensure we convert any Decimal-fields to float for scoring
        for col in df.select_dtypes(include=["object"]).columns:
            try:
                df[col] = df[col].apply(
                    lambda x: float(x) if isinstance(x, Decimal) else x
                )
            except (ValueError, TypeError):
                logger.error(f"Error converting column {col} to float: {e}")
                continue

        # 5) Trust Score
        scorecard = import_scorecard(
            "backend/apps/scoring/initial_trust_scorecard_v1.pkl"
        )
        feature_vector = create_feature_vector(df, scorecard)
        score = float(scorecard.score(feature_vector)[0])

        # 6) Score breakdown
        score_table = scorecard.table()
        factors = score_table.groupby("Variable")["Points"].sum().to_dict()

        # 7) Determine Token Tier
        token_object = CreditTrustBalance.objects.filter(user=user).first()

        # Unified Score Calculation
        # This is a normalized token value between 0 and 100.
        token_norm = min(100, (token_object.balance / TOKEN_MAX) * 100)
        combined_score = (SCORE_WEIGHT * score) + (TOKEN_WEIGHT * token_norm)

        # 8) Affordability & Limit
        limit, apr = calculate_credit_limit(df, combined_score)
        score_tier = _get_score_tier(combined_score)

        # 9) Persist Affordability Snapshot
        AffordabilitySnapshot.objects.create(
            user=user,
            limit=limit,
            apr=apr,
            score_tier=score_tier,
            credit_score=score,
            credit_factors=factors,
            token_score=token_norm,
            combined_score=combined_score,
        )

    except Exception as e:
        # For Celery logs + debugging
        print(f"Error in scoring pipeline for user {user_id}: {e}")
        raise
