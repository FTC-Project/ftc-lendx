import pandas as pd
from backend.apps.scoring.credit_scoring import calculate_affordability, label_data


def limit_apr_gate(score: float) -> float:
    limit, apr = 0, 0
    if score >= 90:
        limit = 100000
        apr = 0.08 # 8%
    if score >= 75:
        limit = 50000
        apr = 0.11 # 11%
    if score >= 45:
        limit = 30000
        apr = 0.15 # 15%
    if score >= 0:
        limit = 10000
        apr = 0.25 # 25%
    return limit, apr


def calculate_affordability_limit(affordability):
    limit = 3 * affordability
    return limit



def calculate_credit_limit(
    transactions: pd.DataFrame, trust_score: float
):
    """Calculates the credit limit and APR based on real data."""
    # Process transaction data
    labeled_transactions = label_data(transactions)
    affordability = calculate_affordability(labeled_transactions, time_window=3)

    # Calculate limit based on trust score and affordability
    limit, apr = limit_apr_gate(trust_score)
    affordability_limit = calculate_affordability_limit(affordability)
    limit = min(limit, affordability_limit)

    return limit, apr
