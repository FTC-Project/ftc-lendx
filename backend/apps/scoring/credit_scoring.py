import pandas as pd
from datetime import datetime
from optbinning import Scorecard


def label_data(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Labels transaction data with additional features for scoring.
    """
    # Rename columns to match what the scoring functions expect
    transactions = transactions.rename(
        columns={"posted_at": "date", "tx_type": "transaction_direction"}
    )
    transactions["transaction_direction"] = transactions["transaction_direction"].apply(
        lambda x: "Incoming" if x == "credit" else "Outgoing"
    )

    transactions["date"] = pd.to_datetime(transactions["date"])
    transactions["transaction_month"] = transactions["date"].dt.to_period("M")
    transactions["transaction_day"] = transactions["date"].dt.to_period("D")

    return transactions


def group_transactions_by_month(
    transactions, add_group=None, variable="amount", apply_func="sum", recency=None
):
    """
    Groups transactions by month and optionally by an additional variable, applying a specified aggregation function.
    """
    if add_group:
        transactions_by_month = (
            transactions.groupby(["transaction_month", add_group])[variable]
            .agg(apply_func)
            .reset_index()
        )
    else:
        transactions_by_month = (
            transactions.groupby("transaction_month")[variable]
            .agg(apply_func)
            .reset_index()
        )

    if recency:
        cutoff_date = pd.to_datetime(
            max(transactions["date"]).strftime("%Y-%m-01")
        ) - pd.DateOffset(months=recency)
        transactions_by_month = transactions_by_month[
            transactions_by_month["transaction_month"] >= cutoff_date.to_period("M")
        ]

    return transactions_by_month


def calculate_affordability(transactions, time_window=6):
    """
    Calculates affordability metrics based on transaction data.
    """
    transactions_grouped = group_transactions_by_month(
        transactions, recency=time_window
    )
    average_affordability = transactions_grouped["amount"].mean()

    return average_affordability


def calculate_savings_buffer(transactions, average_affordability):
    """
    Calculates the savings buffer based on transaction data.
    """
    total_savings = transactions["amount"].sum()
    savings_buffer = (
        total_savings / average_affordability if average_affordability else float("inf")
    )

    return savings_buffer


def months_on_file(transactions):
    """
    Calculates the number of months the user has been on file based on transaction data.
    """
    min_date = transactions["date"].min()
    max_date = datetime.now()
    num_months = (
        (max_date.year - min_date.year) * 12 + (max_date.month - min_date.month) + 1
    )

    return num_months


def calculate_transaction_volume(transactions, time_window=6):
    """
    Calculates the average transaction volume per month.
    """
    transactions_grouped = group_transactions_by_month(
        transactions,
        add_group="transaction_direction",
        variable="id",
        apply_func="count",
        recency=time_window,
    )
    average_volume = transactions_grouped.groupby("transaction_direction")[
        "id"
    ].mean()

    return (
        average_volume.get("Incoming", 0),
        average_volume.get("Outgoing", 0),
    )


def calculate_transaction_frequency(transactions, time_window=6):
    """
    Calculates the average transaction frequency per month.
    """
    if time_window:
        cutoff_date = pd.to_datetime(
            max(transactions["date"]).strftime("%Y-%m-01")
        ) - pd.DateOffset(months=time_window)
        transactions = transactions[
            transactions["transaction_month"] >= cutoff_date.to_period("M")
        ]

    df = transactions.sort_values(by=["date"])
    df["days_since_last"] = (
        df.groupby(["transaction_direction"])["date"]
        .diff()
        .dt.days
    )
    transaction_frequency = df.groupby(["transaction_direction"])[
        "days_since_last"
    ].mean()
    transaction_frequency = transaction_frequency.fillna(0)

    return (
        transaction_frequency.get("Incoming", 0),
        transaction_frequency.get("Outgoing", 0),
    )


def calculate_average_transaction_amount(transactions, time_window=6):
    """
    Calculates the average transaction amount per month.
    """
    transactions_grouped = group_transactions_by_month(
        transactions,
        add_group="transaction_direction",
        apply_func="mean",
        recency=time_window,
    )
    average_amount = transactions_grouped.groupby("transaction_direction")[
        "amount"
    ].mean()

    return (
        average_amount.get("Incoming", 0),
        average_amount.get("Outgoing", 0),
    )


def calculate_average_transaction_variance(transactions, time_window=6):
    """
    Calculates the average transaction variance per month.
    """
    transactions_grouped = group_transactions_by_month(
        transactions,
        add_group="transaction_direction",
        apply_func="var",
        recency=time_window,
    )
    average_variance = transactions_grouped.groupby("transaction_direction")[
        "amount"
    ].mean()

    return (
        average_variance.get("Incoming", 0),
        average_variance.get("Outgoing", 0),
    )


def calculate_expense_to_income_ratio(average_income, average_expenses):
    """
    Calculates the expense to income ratio.
    """
    if average_income == 0:
        return 0
    return -average_expenses / average_income


def import_scorecard(file_path):
    scorecard = Scorecard.load(file_path)
    return scorecard


def create_feature_vector(transactions: pd.DataFrame, scorecard: Scorecard):
    """
    Creates a feature vector for credit scoring based on transaction data.
    """
    labeled_transactions = label_data(transactions)

    avg_affordability = calculate_affordability(labeled_transactions)
    savings_buffer = calculate_savings_buffer(labeled_transactions, avg_affordability)
    months_on_file_value = months_on_file(labeled_transactions)
    avg_incoming_volume, avg_outgoing_volume = calculate_transaction_volume(
        labeled_transactions
    )
    avg_incoming_frequency, avg_outgoing_frequency = calculate_transaction_frequency(
        labeled_transactions
    )
    avg_incoming_amount, avg_outgoing_amount = calculate_average_transaction_amount(
        labeled_transactions
    )
    var_incoming_amount, var_outgoing_amount = calculate_average_transaction_variance(
        labeled_transactions
    )
    expense_to_income_ratio = calculate_expense_to_income_ratio(
        avg_incoming_amount, avg_outgoing_amount
    )

    feature_vector = {
        "average_affordability": avg_affordability,
        "affordability_buffer": savings_buffer,
        "months_on_book": months_on_file_value,
        "incoming_volume": avg_incoming_volume,
        "outgoing_volume": avg_outgoing_volume,
        "incoming_frequency": avg_incoming_frequency,
        "outgoing_frequency": avg_outgoing_frequency,
        "average_incoming_amount": avg_incoming_amount,
        "average_outgoing_amount": avg_outgoing_amount,
        "incoming_variance": var_incoming_amount,
        "outgoing_variance": var_outgoing_amount,
        "direction_ratio": expense_to_income_ratio,
    }

    return pd.DataFrame(feature_vector, index=[0])
