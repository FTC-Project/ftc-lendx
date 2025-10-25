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
from backend.apps.banking.models import BankAccount, BankTransaction, OAuthToken
from backend.apps.loans.models import Loan
from backend.apps.scoring.credit_scoring import create_feature_vector, import_scorecard
from backend.apps.scoring.limit import calculate_credit_limit
from backend.apps.scoring.models import (
    AffordabilitySnapshot,
    RiskTier,
    TrustScoreSnapshot,
)
from backend.apps.tokens.models import CreditTrustBalance
from backend.apps.users.crypto import decrypt_secret
from backend.apps.users.models import TelegramUser


# ---------------------------
# Helpers
# ---------------------------


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
        raise ValueError("Transactions payload 'data' key is not a list.")
    if isinstance(payload, list):
        return payload
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
) -> list[dict]:
    """
    Robustly fetch *all* transactions, following pagination by 'next_cursor' if present.
    Returns the concatenated list in the *external* shape (not normalized).
    """
    all_txs: list[dict] = []
    after: Optional[str] = None

    while True:
        page = client.list_transactions_all(
            access_token=access_token,
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

    return all_txs


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
        bank_account = BankAccount.objects.filter(user=user).first()  # Just get one account for now

        if not bank_account:
            raise ValueError("No valid bank account found for user.")

        # 1) OAuth & Client
        oauth_token = OAuthToken.objects.get(user=user)
        if not oauth_token or not oauth_token.access_token_enc:
            raise ValueError("No valid OAuth token found for user.")
        access_token = decrypt_secret(oauth_token.access_token_enc)
        client = AISClient()

        # 2) Fetch ALL transactions (with pagination if provided by API)
        ext_txs = _fetch_all_transactions(
            client=client,
            access_token=access_token,
            from_date="1900-01-01",
            to_date="2100-12-31",
            page_limit=None,  # or set e.g. 500 if backend enforces a maximum
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

        user_transactions = BankTransaction.objects.filter(account__user=user).values()
        df = pd.DataFrame(list(user_transactions))

        DataAccessLog.objects.create(
            user=user,
            actor="system",
            resource="banking.transactions",
            action="read",
            context={"purpose": "credit_scoring"},
        )

        # Guard: empty datasets shouldn't crash scoring
        if df.empty:
            # Create a minimal snapshot to record that we attempted scoring but had no data
            trust_score_snapshot = TrustScoreSnapshot.objects.create(
                user=user,
                trust_score=0.0,
                factors={},
                risk_category="Insufficient Data",
            )
            AffordabilitySnapshot.objects.create(
                user=user,
                limit=Decimal("0"),
                apr=Decimal("0"),
                token_tier="New",
                trust_score_snapshot=trust_score_snapshot,
            )
            return  # Nothing else to do

        # Ensure we convert any Decimal-fields to float for scoring
        for col in df.select_dtypes(include=["object"]).columns:
            try:
                df[col] = df[col].apply(
                    lambda x: float(x) if isinstance(x, Decimal) else x
                )
            except (ValueError, TypeError):
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

        risk_tier = RiskTier.objects.filter(
            min_score__lte=score, max_score__gte=score
        ).first()
        risk_category = risk_tier.name if risk_tier else "High Risk"

        trust_score_snapshot = TrustScoreSnapshot.objects.create(
            user=user, trust_score=score, factors=factors, risk_category=risk_category
        )

        # 7) Determine Token Tier
        token_balance = CreditTrustBalance.objects.filter(user=user).first()
        has_active_loan = Loan.objects.filter(
            user=user, state__in=["funded", "disbursed"]
        ).exists()

        if not token_balance or token_balance.balance == 0:
            token_tier = "New" if not has_active_loan else "High Risk"
        elif token_balance.balance <= 100:
            token_tier = "Good"
        else:
            token_tier = "Excellent"

        # 8) Affordability & Limit
        limit, apr = calculate_credit_limit(df, score, token_tier)

        # 9) Persist Affordability Snapshot
        AffordabilitySnapshot.objects.create(
            user=user,
            limit=limit,
            apr=apr,
            token_tier=token_tier,
            trust_score_snapshot=trust_score_snapshot,
        )

    except Exception as e:
        # For Celery logs + debugging
        print(f"Error in scoring pipeline for user {user_id}: {e}")
        raise
