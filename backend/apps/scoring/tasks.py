import pandas as pd
from celery import shared_task
from django.utils.dateparse import parse_datetime

from backend.apps.audit.models import DataAccessLog
from backend.apps.banking.adapters import AISClient
from backend.apps.banking.models import BankAccount, BankTransaction, OAuthToken
from backend.apps.loans.models import Loan
from backend.apps.scoring.credit_scoring import create_feature_vector, import_scorecard
from backend.apps.scoring.limit import calculate_credit_limit
from backend.apps.scoring.models import AffordabilitySnapshot, RiskTier, TrustScoreSnapshot
from backend.apps.tokens.models import CreditTrustBalance
from backend.apps.users.crypto import decrypt_secret
from backend.apps.users.models import TelegramUser


@shared_task(queue="scoring")
def start_scoring_pipeline(user_id: int, bank_account_id: int):
    """Starts the credit scoring and affordability calculation pipeline."""
    try:
        user = TelegramUser.objects.get(id=user_id)
        bank_account = BankAccount.objects.get(id=bank_account_id)

        # 1. Fetch and Persist Transactions
        # ----------------------------------
        oauth_token = OAuthToken.objects.get(user=user)
        access_token = decrypt_secret(oauth_token.access_token_enc).decode("utf-8")

        client = AISClient()
        transactions_data = client.list_transactions_all(
            access_token=access_token, from_date="1900-01-01", to_date="2100-12-31")
        # TODO: Actually implement this kak.

        for tx in transactions_data:
            BankTransaction.objects.update_or_create(
                id=tx.get("transactionId"),
                defaults={
                    "account": bank_account,
                    "posted_at": parse_datetime(tx.get("postingDateTime")),
                    "description": tx.get("transactionInformation"),
                    "amount": tx.get("amount"),
                    "tx_type": "credit" if float(tx.get("amount")) > 0 else "debit",
                    "category": tx.get("merchantDetails", {}).get("merchantCategoryCode"),
                    "raw": tx,
                },
            )

        DataAccessLog.objects.create(
            user=user,
            actor="system",
            resource="banking.transactions",
            action="write",
            context={"count": len(transactions_data), "bank_account_id": bank_account_id},
        )

        # 2. Prepare data for scoring
        # ---------------------------
        user_transactions = BankTransaction.objects.filter(account__user=user).values()
        df = pd.DataFrame(list(user_transactions))

        DataAccessLog.objects.create(
            user=user,
            actor="system",
            resource="banking.transactions",
            action="read",
            context={"purpose": "credit_scoring"},
        )

        # 3. Calculate Trust Score
        # ------------------------
        scorecard = import_scorecard("backend/apps/scoring/initial_trust_scorecard_v1.pkl")
        feature_vector = create_feature_vector(df, scorecard)
        score = scorecard.score(feature_vector)[0]

        # 4. Get Score Breakdown
        # ----------------------
        score_table = scorecard.table(feature_vector)
        factors = score_table.groupby("Variable")["Points"].sum().to_dict()

        #TODO: Add this to the DB at some point so we have some history
        risk_tier = RiskTier.objects.filter(min_score__lte=score, max_score__gte=score).first()
        risk_category = risk_tier.name if risk_tier else "High Risk"

        trust_score_snapshot = TrustScoreSnapshot.objects.create(
            user=user, trust_score=score, factors=factors, risk_category=risk_category
        )

        # 5. Determine Token Tier
        # -----------------------
        token_balance = CreditTrustBalance.objects.filter(user=user).first()
        has_active_loan = Loan.objects.filter(
            user=user, state__in=["funded", "disbursed"]
        ).exists()

        token_tier = ""
        if not token_balance or token_balance.balance == 0:
            token_tier = "New" if not has_active_loan else "High Risk"
        elif token_balance.balance <= 100:
            token_tier = "Good"
        else:
            token_tier = "Excellent"

        # 6. Calculate Affordability & Limit
        # ----------------------------------
        limit, apr = calculate_credit_limit(df, score, token_tier)

        # 7. Save Affordability Snapshot
        # ------------------------------
        AffordabilitySnapshot.objects.create(
            user=user,
            limit=limit,
            apr=apr,
            token_tier=token_tier,
            trust_score_snapshot=trust_score_snapshot,
        )

    except Exception as e:
        # TODO: Add more robust error handling and logging
        print(f"Error in scoring pipeline for user {user_id}: {e}")
        raise