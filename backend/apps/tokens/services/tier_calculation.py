# token_tiers.py

from typing import Dict


class TokenTierCalculator:
    """
    Calculates token tier information based on token balance.
    """

    TIERS = [
        {"name": "Excellent", "min_balance": 201, "max_loan": 7500, "base_apr": 15},
        {"name": "Good", "min_balance": 121, "max_loan": 5000, "base_apr": 20},
        {"name": "New", "min_balance": 100, "max_loan": 2000, "base_apr": 25},
        {"name": "Medium Risk", "min_balance": 20, "max_loan": 1500, "base_apr": 30},
        {"name": "High Risk", "min_balance": 0, "max_loan": 500, "base_apr": 35},
    ]

    def __init__(self, token_balance: int):
        if token_balance < 0:
            raise ValueError("Token balance cannot be negative.")
        self.token_balance = token_balance

    def get_tier(self) -> Dict[str, any]:
        for tier in self.TIERS:
            if self.token_balance >= tier["min_balance"]:
                return {
                    "tier": tier["name"],
                    "max_loan": tier["max_loan"],
                    "base_apr": tier["base_apr"],
                }
        # Fallback (should not happen)
        return {"tier": "Unknown", "max_loan": 0, "base_apr": 0}