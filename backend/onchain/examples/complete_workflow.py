"""
Complete Lending Workflow Example
==================================

This script demonstrates a complete lending cycle:
1. Admin mints FTCT to lender and borrower
2. Lender deposits FTCT into the pool
3. Admin creates, funds, and disburses a loan
4. Borrower repays the loan
5. Lender withdraws from the pool with interest

Usage:
    python backend/onchain/examples/complete_workflow.py
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from backend.apps.tokens.services import (
    FTCTokenService,
    LoanSystemService,
    CreditTrustTokenService,
)
from django.conf import settings
from decimal import Decimal

# Test accounts (Hardhat default accounts)
LENDER = {
    'address': '0x70997970C51812dc3A010C7d01b50e0d17dc79C8',
    'private_key': '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d',
}

BORROWER = {
    'address': '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC',
    'private_key': '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a',
}


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_step(step_num, text):
    """Print formatted step"""
    print(f"\n📍 Step {step_num}: {text}")
    print("-" * 80)


def main():
    """Run the complete workflow"""
    
    print_header("Complete Lending Workflow")
    
    # Initialize services
    ftc = FTCTokenService()
    loan = LoanSystemService()
    ctt = CreditTrustTokenService()
    
    print(f"🔗 Connected to: {ftc.web3.provider.endpoint_uri}")
    print(f"🌐 Chain ID: {ftc.web3.eth.chain_id}")
    print(f"📦 Block number: {ftc.get_block_number()}")
    
    # -------------------------------------------------------------------------
    # STEP 1: Mint FTCT tokens
    # -------------------------------------------------------------------------
    print_step(1, "Mint FTCT tokens")
    
    print(f"Minting 5000 FTCT to lender ({LENDER['address']})...")
    result = ftc.mint(LENDER['address'], 5000.0)
    print(f"✅ Tx: {result['tx_hash']}")
    
    print(f"\nMinting 1000 FTCT to borrower ({BORROWER['address']})...")
    result = ftc.mint(BORROWER['address'], 1000.0)
    print(f"✅ Tx: {result['tx_hash']}")
    
    lender_balance = ftc.get_balance(LENDER['address'])
    borrower_balance = ftc.get_balance(BORROWER['address'])
    
    print(f"\n💰 Lender balance: {lender_balance} FTCT")
    print(f"💰 Borrower balance: {borrower_balance} FTCT")
    
    # -------------------------------------------------------------------------
    # STEP 2: Lender deposits into pool
    # -------------------------------------------------------------------------
    print_step(2, "Lender deposits into pool")
    
    deposit_amount = 2000.0
    
    print(f"Approving LoanSystem to spend {deposit_amount} FTCT...")
    result = ftc.approve(
        owner_address=LENDER['address'],
        spender_address=settings.LOANSYSTEM_ADDRESS,
        amount=deposit_amount,
        private_key=LENDER['private_key'],
    )
    print(f"✅ Approved: {result['tx_hash']}")
    
    print(f"\nDepositing {deposit_amount} FTCT into pool...")
    result = loan.deposit_ftct(
        lender_address=LENDER['address'],
        amount=deposit_amount,
        lender_private_key=LENDER['private_key'],
    )
    print(f"✅ Deposited: {result['tx_hash']}")
    
    lender_shares = loan.get_shares_of(LENDER['address'])
    total_pool = loan.get_total_pool()
    
    print(f"\n📊 Lender shares: {lender_shares}")
    print(f"📊 Total pool: {total_pool} FTCT")
    
    # -------------------------------------------------------------------------
    # STEP 3: Admin creates a loan
    # -------------------------------------------------------------------------
    print_step(3, "Admin creates a loan")
    
    loan_amount = 500.0
    apr_bps = 1200  # 12% APR
    term_days = 30
    
    print(f"Creating loan for borrower:")
    print(f"  Amount: {loan_amount} FTCT")
    print(f"  APR: {apr_bps / 100}%")
    print(f"  Term: {term_days} days")
    
    loan_id, result = loan.create_loan(
        borrower_address=BORROWER['address'],
        amount=loan_amount,
        apr_bps=apr_bps,
        term_days=term_days,
    )
    print(f"✅ Created loan ID {loan_id}: {result['tx_hash']}")
    
    # Get loan details
    loan_details = loan.get_loan(loan_id)
    print(f"\n📋 Loan Details:")
    print(f"  ID: {loan_id}")
    print(f"  Borrower: {loan_details['borrower']}")
    print(f"  Principal: {loan_details['principal']} FTCT")
    print(f"  APR: {loan_details['apr_bps'] / 100}%")
    print(f"  Term: {loan_details['term_days']} days")
    print(f"  State: {loan_details['state_name']}")
    
    # -------------------------------------------------------------------------
    # STEP 4: Admin funds the loan
    # -------------------------------------------------------------------------
    print_step(4, "Admin funds the loan")
    
    print(f"Marking loan {loan_id} as funded (reserving pool funds)...")
    result = loan.mark_funded(loan_id)
    print(f"✅ Funded: {result['tx_hash']}")
    
    total_pool_after_fund = loan.get_total_pool()
    print(f"\n📊 Total pool after funding: {total_pool_after_fund} FTCT")
    
    # -------------------------------------------------------------------------
    # STEP 5: Admin disburses the loan
    # -------------------------------------------------------------------------
    print_step(5, "Admin disburses the loan to borrower")
    
    borrower_balance_before = ftc.get_balance(BORROWER['address'])
    print(f"Borrower balance before disbursement: {borrower_balance_before} FTCT")
    
    print(f"\nDisbursing loan {loan_id}...")
    result = loan.mark_disbursed_ftct(loan_id)
    print(f"✅ Disbursed: {result['tx_hash']}")
    
    borrower_balance_after = ftc.get_balance(BORROWER['address'])
    print(f"Borrower balance after disbursement: {borrower_balance_after} FTCT")
    print(f"Received: {borrower_balance_after - borrower_balance_before} FTCT")
    
    # Check loan state
    loan_details = loan.get_loan(loan_id)
    print(f"\n📋 Loan state: {loan_details['state_name']}")
    print(f"Due date (timestamp): {loan_details['due_date']}")
    
    # -------------------------------------------------------------------------
    # STEP 6: Borrower repays the loan
    # -------------------------------------------------------------------------
    print_step(6, "Borrower repays the loan")
    
    # Calculate repayment
    interest = loan.calculate_interest(
        principal=loan_amount,
        apr_bps=apr_bps,
        term_days=term_days,
    )
    total_due = Decimal(loan_amount) + interest
    
    print(f"Repayment calculation:")
    print(f"  Principal: {loan_amount} FTCT")
    print(f"  Interest: {interest} FTCT")
    print(f"  Total due: {total_due} FTCT")
    
    # Approve LoanSystem to spend repayment
    print(f"\nApproving LoanSystem to spend {total_due} FTCT...")
    result = ftc.approve(
        owner_address=BORROWER['address'],
        spender_address=settings.LOANSYSTEM_ADDRESS,
        amount=float(total_due),
        private_key=BORROWER['private_key'],
    )
    print(f"✅ Approved: {result['tx_hash']}")
    
    # Repay loan
    print(f"\nRepaying loan {loan_id}...")
    result = loan.mark_repaid_ftct(
        loan_id=loan_id,
        on_time=True,
        amount=float(total_due),
        borrower_address=BORROWER['address'],
        borrower_private_key=BORROWER['private_key'],
    )
    print(f"✅ Repaid: {result['tx_hash']}")
    
    # Check borrower's final balance
    borrower_final_balance = ftc.get_balance(BORROWER['address'])
    print(f"\n💰 Borrower final balance: {borrower_final_balance} FTCT")
    
    # Check borrower's reputation
    borrower_ctt = ctt.get_balance(BORROWER['address'])
    print(f"🏆 Borrower reputation (CTT): {borrower_ctt}")
    
    # Check pool after repayment
    total_pool_after_repay = loan.get_total_pool()
    print(f"\n📊 Pool after repayment: {total_pool_after_repay} FTCT")
    print(f"📊 Interest earned by pool: {total_pool_after_repay - total_pool_after_fund} FTCT")
    
    # -------------------------------------------------------------------------
    # STEP 7: Lender withdraws from pool
    # -------------------------------------------------------------------------
    print_step(7, "Lender withdraws from pool")
    
    lender_shares_before = loan.get_shares_of(LENDER['address'])
    shares_to_withdraw = float(lender_shares_before)
    
    print(f"Lender has {lender_shares_before} shares")
    print(f"Withdrawing all shares...")
    
    result = loan.withdraw_ftct(
        lender_address=LENDER['address'],
        share_amount=shares_to_withdraw,
        lender_private_key=LENDER['private_key'],
    )
    print(f"✅ Withdrew {result['ftct_amount']} FTCT: {result['tx_hash']}")
    
    # Check final balances
    lender_final_balance = ftc.get_balance(LENDER['address'])
    lender_final_shares = loan.get_shares_of(LENDER['address'])
    
    print(f"\n💰 Lender final FTCT balance: {lender_final_balance}")
    print(f"📊 Lender final shares: {lender_final_shares}")
    print(f"💸 Lender profit: {lender_final_balance - lender_balance} FTCT")
    
    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print_header("Workflow Summary")
    
    print("✅ Complete workflow executed successfully!\n")
    print("📊 Final State:")
    print(f"  Lender FTCT balance: {lender_final_balance}")
    print(f"  Lender profit: {lender_final_balance - lender_balance} FTCT")
    print(f"  Borrower FTCT balance: {borrower_final_balance}")
    print(f"  Borrower reputation (CTT): {borrower_ctt}")
    print(f"  Pool balance: {loan.get_total_pool()} FTCT")
    print(f"  Loan state: {loan.get_loan(loan_id)['state_name']}")
    
    print("\n🎉 Workflow complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Workflow interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

