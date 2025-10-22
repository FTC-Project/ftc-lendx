import pandas as pd
from backend.apps.scoring.credit_scoring import calculate_affordability, label_data


def calculate_trust_score_limit(trust_score):
    if trust_score >= 80:
        limit = 2000
    elif 80 > trust_score >= 60:
        limit = 1500
    elif 60 > trust_score >= 40:
        limit = 1000
    else:
        limit = 500
    return limit


def calculate_affordability_limit(affordability):
    limit = 3 * affordability
    return limit


def calculate_apr(token_tier):
    if token_tier == "Excellent":
        apr = 0.15
    elif token_tier == "Good":
        apr = 0.2
    elif token_tier == "New":
        apr = 0.25
    else:  # High Risk
        apr = 0.35
    return apr


def calculate_credit_limit(
    transactions: pd.DataFrame, trust_score: float, token_tier: str
):
    """Calculates the credit limit and APR based on real data."""
    # Process transaction data
    labeled_transactions = label_data(transactions)
    affordability = calculate_affordability(labeled_transactions, time_window=3)

    # Calculate limit based on trust score and affordability
    trust_score_gate = calculate_trust_score_limit(trust_score)
    affordability_gate = calculate_affordability_limit(affordability)
    limit = min(trust_score_gate, affordability_gate)

    # Calculate APR based on token tier
    apr = calculate_apr(token_tier)

    return limit, apr
