import pandas as pd
from backend.apps.scoring.credit_scoring import calculate_affordability, label_data


def limit_apr_gate(score: float) -> float:
    """Returns limit and APR based on score tier. Uses elif for exclusive matching."""
    limit, apr = 0, 0
    if score >= 90:
        limit = 100000
        apr = 0.08  # 8%
    elif score >= 75:
        limit = 50000
        apr = 0.11  # 11%
    elif score >= 45:
        limit = 30000
        apr = 0.15  # 15%
    elif score >= 0:
        # For very low scores, scale down the limit proportionally
        # Score 0-44 gets between 5K and 10K based on their score
        if score < 20:
            limit = 5000  # Very risky: minimum limit
            apr = 0.25  # 25%
        else:
            # Scale linearly from 5K (at score 20) to 10K (at score 45)
            limit = 5000 + ((score - 20) / (45 - 20)) * (10000 - 5000)
            apr = 0.25  # 25%
    return limit, apr


def calculate_affordability_limit(affordability):
    limit = 3 * affordability
    return limit


def calculate_credit_limit(transactions: pd.DataFrame, trust_score: float):
    """Calculates the credit limit and APR based on real data."""
    # Process transaction data
    labeled_transactions = label_data(transactions)
    affordability = calculate_affordability(labeled_transactions, time_window=3)

    # Calculate limit based on trust score and affordability
    limit, apr = limit_apr_gate(trust_score)
    
    # Calculate affordability-based cap (3x monthly affordability)
    # Only consider positive affordability - negative means they can't afford loans
    if affordability > 0:
        affordability_limit = calculate_affordability_limit(affordability)
        # Cap the score-based limit by what they can actually afford
        limit = min(limit, affordability_limit)
    else:
        # Negative affordability means they're spending more than they earn
        # Set limit to 0 regardless of score
        limit = 0
    
    # Ensure limit is never negative (safety check)
    limit = max(limit, 0)

    return limit, apr
