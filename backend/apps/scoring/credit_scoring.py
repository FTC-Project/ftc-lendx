import pandas as pd
from datetime import datetime
from optbinning import Scorecard

def import_transaction_data(file_path):
    transactions = pd.read_csv(file_path)
    return transactions

def label_data(transactions):
    '''
    Labels transaction data with additional features such as transaction direction, month, and day.
    
    Parameters:
    transactions (pd.DataFrame): DataFrame containing transaction data with at least 'amount' 
    and 'date' columns. All transactions should be from a single user.

    Returns:
    pd.DataFrame: DataFrame with labeled transaction data.
    '''

    transactions['transaction_direction'] = transactions['amount'].apply(lambda x: 'Incoming' if x > 0 else 'Outgoing')
    transactions['date'] = pd.to_datetime(transactions['date'])
    transactions['transaction_month'] = transactions['date'].dt.to_period('M')
    transactions['transaction_day'] = transactions['date'].dt.to_period('D')
    
    return transactions

def group_transactions_by_month(transactions, add_group=None, variable='amount', apply_func='sum', recency=None):
    '''
    Groups transactions by month and optionally by an additional variable, applying a specified aggregation function.  

    Parameters:
    transactions (pd.DataFrame): DataFrame containing labeled transaction data.
    variable (str): Column name to group by in addition to month.
    add_group (str or None): Additional column name to group by. If None, only
    groups by month.
    apply_func (str): Aggregation function to apply ('sum', 'mean', etc.).

    Returns:
    pd.DataFrame: DataFrame with transactions grouped by month (and additional variable if specified).
    '''         

    if add_group:
        transactions_by_month = transactions.groupby(['transaction_month', add_group])[variable].agg(apply_func).reset_index()
    else:
        transactions_by_month = transactions.groupby('transaction_month')[variable].agg(apply_func).reset_index()

    if recency:
        cutoff_date = pd.to_datetime(max(transactions['date']).strftime('%Y-%m-01')) - pd.DateOffset(months=recency)
        transactions_by_month = transactions_by_month[transactions_by_month['transaction_month'] >= cutoff_date.to_period('M')]

    return transactions_by_month
        
def calculate_affordability(transactions, time_window=6):
    '''
    Calculates affordability metrics based on transaction data.
    
    Parameters:
    transactions (pd.DataFrame): DataFrame containing labeled transaction data.
    time_window (int): The number of months to consider for the affordability calculation.

    Returns:
    dict: Dictionary containing affordability metrics.
    '''

    transactions_grouped = group_transactions_by_month(transactions, recency=time_window)
    average_affordability = transactions_grouped['amount'].mean()

    return average_affordability

def calculate_savings_buffer(transactions, average_affordability):
    '''
    Calculates the savings buffer based on transaction data.
    
    Parameters:
    transactions (pd.DataFrame): DataFrame containing labeled transaction data.
    average_affordability (float): Average affordability metric.

    Returns:
    float: Savings buffer in months.
    '''

    total_savings = transactions['amount'].sum()
    savings_buffer = total_savings / average_affordability if average_affordability else float('inf')

    return savings_buffer

def months_on_file(transactions):
    '''
    Calculates the number of months the user has been on file based on transaction data.
    
    Parameters:
    transactions (pd.DataFrame): DataFrame containing labeled transaction data.

    Returns:
    int: Number of months on file.
    '''

    min_date = transactions['date'].min()
    max_date = datetime.now()
    num_months = (max_date.year - min_date.year) * 12 + (max_date.month - min_date.month) + 1

    return num_months

def calculate_transaction_volume(transactions, time_window=6):
    '''
    Calculates the average transaction volume per month.

    Parameters:
    transactions (pd.DataFrame): DataFrame containing labeled transaction data.

    Returns:
    float: Average transaction volume per month, incoming and outgoing combined.
    '''

    transactions_grouped = group_transactions_by_month(transactions, add_group='transaction_direction', variable='transaction_id', apply_func='count', recency=time_window)
    average_volume = transactions_grouped.groupby('transaction_direction')['transaction_id'].mean()

    return average_volume[average_volume.index == 'Incoming'].values[0], average_volume[average_volume.index == 'Outgoing'].values[0]

def calculate_transaction_frequency(transactions, time_window=6):
    '''
    Calculates the average transaction frequency per month.

    Parameters:
    transactions (pd.DataFrame): DataFrame containing labeled transaction data.

    Returns:
    float: Average transaction frequency per month, incoming and outgoing combined.
    '''
    
    if time_window:
        cutoff_date = pd.to_datetime(max(transactions['date']).strftime('%Y-%m-01')) - pd.DateOffset(months=time_window)
        transactions = transactions[transactions['transaction_month'] >= cutoff_date.to_period('M')]

    # Sort by client and date
    df = transactions.sort_values(by=["date"])

    # Compute days since last transaction for each client + direction
    df["days_since_last"] = (
        df.groupby(["transaction_direction"])["date"]
        .diff()  # timedelta between current and previous transaction
        .dt.days  # convert to number of days
    )

    # Compute average transaction frequency (mean days between transactions)
    transaction_frequency = (
        df.groupby(["transaction_direction"])["days_since_last"]
        .mean()
    )

    # Fill missing values with 0 if a client has only one type of transaction
    transaction_frequency = transaction_frequency.fillna(0)

    return transaction_frequency[transaction_frequency.index == 'Incoming'].values[0], transaction_frequency[transaction_frequency.index == 'Outgoing'].values[0]

def calculate_average_transaction_amount(transactions, time_window=6):
    '''
    Calculates the average transaction amount per month.
    
    Parameters:
    transactions (pd.DataFrame): DataFrame containing labeled transaction data.

    Returns:
    float: Average transaction amount per month, incoming and outgoing combined.
    '''

    transactions_grouped = group_transactions_by_month(transactions, add_group='transaction_direction', apply_func='mean', recency=time_window)
    average_frequency = transactions_grouped.groupby('transaction_direction')['amount'].mean()

    return average_frequency[average_frequency.index == 'Incoming'].values[0], average_frequency[average_frequency.index == 'Outgoing'].values[0]

def calculate_average_transaction_variance(transactions, time_window=6):
    '''
    Calculates the average transaction variance per month.

    Parameters:
    transactions (pd.DataFrame): DataFrame containing labeled transaction data.

    Returns:
    float: Average transaction variance per month, incoming and outgoing combined.
    '''

    transactions_grouped = group_transactions_by_month(transactions, add_group='transaction_direction', apply_func='var', recency=time_window)
    average_variance = transactions_grouped.groupby('transaction_direction')['amount'].mean()

    return average_variance[average_variance.index == 'Incoming'].values[0], average_variance[average_variance.index == 'Outgoing'].values[0]

def calculate_expense_to_income_ratio(average_income, average_expenses):
    '''
    Calculates the expense to income ratio. 

    Parameters:
    average_income (float): Average income over the time window.
    average_expenses (float): Average expenses over the time window.

    Returns:
    float: Expense to income ratio.
    '''

    expense_to_income_ratio = - average_expenses / average_income

    return expense_to_income_ratio

def import_scorecard(file_path):
    scorecard = Scorecard.load(file_path)
    return scorecard

def create_feature_vector(transactions, scorecard):
    '''
    Creates a feature vector for credit scoring based on transaction data and a scorecard.

    Parameters:
    transactions (pd.DataFrame): DataFrame containing labeled transaction data.
    scorecard (pd.DataFrame): DataFrame containing the scorecard with feature weights.

    Returns:
    dict: Feature vector with calculated metrics.
    '''

    avg_affordability = calculate_affordability(transactions)
    savings_buffer = calculate_savings_buffer(transactions, avg_affordability)
    months_on_file_value = months_on_file(transactions)
    avg_incoming_volume, avg_outgoing_volume = calculate_transaction_volume(transactions)
    avg_incoming_frequency, avg_outgoing_frequency = calculate_transaction_frequency(transactions)
    avg_incoming_amount, avg_outgoing_amount = calculate_average_transaction_amount(transactions)
    var_incoming_amount, var_outgoing_amount = calculate_average_transaction_variance(transactions)
    expense_to_income_ratio = calculate_expense_to_income_ratio(avg_incoming_amount, avg_outgoing_amount)

    feature_vector = {
        'average_affordability': avg_affordability, 
        'affordability_buffer': savings_buffer,
        'months_on_book': months_on_file_value, 
        'incoming_volume': avg_incoming_volume,
        'outgoing_volume': avg_outgoing_volume,
        'incoming_frequency': avg_incoming_frequency,
        'outgoing_frequency': avg_outgoing_frequency,
        'average_incoming_amount': avg_incoming_amount,
        'average_outgoing_amount': avg_outgoing_amount,
        'incoming_variance': var_incoming_amount,
        'outgoing_variance': var_outgoing_amount,
        'direction_ratio': expense_to_income_ratio
    }

    return pd.DataFrame(feature_vector, index=[0])

def calculate_credit_score(feature_vector, scorecard):
    '''
    Calculates the credit score based on the feature vector and scorecard.

    Parameters:
    feature_vector (dict): Dictionary containing calculated metrics.
    scorecard (pd.DataFrame): DataFrame containing the scorecard with feature weights.

    Returns:
    float: Calculated credit score.
    '''

    credit_score = scorecard.score(feature_vector)

    return credit_score[0]

def calculate_trust_score(transaction_file_path, scorecard_file_path):
    transactions = import_transaction_data(transaction_file_path)
    labeled_transactions = label_data(transactions)
    scorecard = import_scorecard(scorecard_file_path)
    feature_vector = create_feature_vector(labeled_transactions, scorecard)
    credit_score = calculate_credit_score(feature_vector, scorecard)

    return credit_score