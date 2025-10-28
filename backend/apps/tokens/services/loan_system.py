"""
LoanSystemMVP Contract Service
Handles pool deposits, withdrawals, loan lifecycle, and liquidity management
"""

from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
from django.conf import settings
import logging
from .base_contract import BaseContractService

logger = logging.getLogger(__name__)


class LoanSystemService(BaseContractService):
    """Service for interacting with the LoanSystemMVP contract"""
    
    # Loan states
    STATE_CREATED = 0
    STATE_FUNDED = 1
    STATE_DISBURSED = 2
    STATE_REPAID = 3
    STATE_DEFAULTED = 4
    
    STATE_NAMES = {
        0: "Created",
        1: "Funded",
        2: "Disbursed",
        3: "Repaid",
        4: "Defaulted",
    }
    
    def __init__(self):
        super().__init__(
            contract_address=settings.LOANSYSTEM_ADDRESS,
            abi_path=settings.LOANSYSTEM_ABI_PATH,
        )
    
    # ============================================================
    # READ-ONLY FUNCTIONS - Pool
    # ============================================================
    
    def get_total_pool(self) -> Decimal:
        """Get total pool balance in FTCT"""
        pool_wei = self.call_read_function('totalPool')
        return self.from_wei(pool_wei)
    
    def get_total_shares(self) -> Decimal:
        """Get total pool shares"""
        shares_wei = self.call_read_function('totalShares')
        return self.from_wei(shares_wei)
    
    def get_shares_of(self, address: str) -> Decimal:
        """
        Get pool shares of an address
        
        Args:
            address: Lender address
            
        Returns:
            Number of shares (Decimal)
        """
        address = self.checksum_address(address)
        shares_wei = self.call_read_function('sharesOf', address)
        return self.from_wei(shares_wei)
    
    def get_share_value(self, shares: float) -> Decimal:
        """
        Calculate FTCT value of given shares
        
        Args:
            shares: Number of shares
            
        Returns:
            FTCT value (Decimal)
        """
        total_pool = self.get_total_pool()
        total_shares = self.get_total_shares()
        
        if total_shares == 0:
            return Decimal(0)
        
        return Decimal(shares) * total_pool / total_shares
    
    def get_admin(self) -> str:
        """Get admin address"""
        return self.call_read_function('admin')
    
    # ============================================================
    # READ-ONLY FUNCTIONS - Loans
    # ============================================================
    
    def get_loan(self, loan_id: int) -> Dict[str, Any]:
        """
        Get loan details
        
        Args:
            loan_id: Loan ID
            
        Returns:
            Dict with loan details
        """
        loan_data = self.call_read_function('loans', loan_id)
        
        return {
            'borrower': loan_data[0],
            'principal': self.from_wei(loan_data[1]),
            'apr_bps': loan_data[2],
            'term_days': loan_data[3],
            'state': loan_data[4],
            'state_name': self.STATE_NAMES.get(loan_data[4], 'Unknown'),
            'escrow_balance': self.from_wei(loan_data[5]),
            'due_date': loan_data[6],
        }
    
    def get_next_loan_id(self) -> int:
        """Get next loan ID"""
        return self.call_read_function('nextId')
    
    def calculate_interest(
        self,
        principal: float,
        apr_bps: int,
        term_days: int
    ) -> Decimal:
        """
        Calculate simple interest for a loan
        
        Args:
            principal: Loan principal in FTCT
            apr_bps: Annual percentage rate in basis points (e.g., 1200 = 12%)
            term_days: Loan term in days
            
        Returns:
            Interest amount in FTCT (Decimal)
        """
        principal_wei = self.to_wei(principal)
        interest_wei = self.call_read_function(
            '_calcInterest',
            principal_wei,
            apr_bps,
            term_days
        )
        return self.from_wei(interest_wei)
    
    # ============================================================
    # WRITE FUNCTIONS - Pool (Lenders)
    # ============================================================
    
    def deposit_ftct(
        self,
        lender_address: str,
        amount: float,
        lender_private_key: str
    ) -> Dict[str, Any]:
        """
        Deposit FTCT into the pool
        Note: Lender must approve LoanSystem to spend FTCT first
        
        Args:
            lender_address: Lender address
            amount: Amount of FTCT to deposit
            lender_private_key: Lender's private key
            
        Returns:
            Transaction details
        """
        amount_wei = self.to_wei(amount)
        
        logger.info(f"Depositing {amount} FTCT to pool from {lender_address}")
        
        function = self.contract.functions.depositFTCT(amount_wei)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=lender_address,
            private_key=lender_private_key,
        )
        
        logger.info(f"Deposited {amount} FTCT (tx: {result['tx_hash']})")
        return result
    
    def withdraw_ftct(
        self,
        lender_address: str,
        share_amount: float,
        lender_private_key: str
    ) -> Dict[str, Any]:
        """
        Withdraw FTCT from the pool by redeeming shares
        
        Args:
            lender_address: Lender address
            share_amount: Number of shares to redeem
            lender_private_key: Lender's private key
            
        Returns:
            Transaction details including FTCT amount received
        """
        share_amount_wei = self.to_wei(share_amount)
        
        # Calculate expected FTCT amount
        ftct_amount = self.get_share_value(share_amount)
        
        logger.info(f"Withdrawing {share_amount} shares (~{ftct_amount} FTCT) from {lender_address}")
        
        function = self.contract.functions.withdrawFTCT(share_amount_wei)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=lender_address,
            private_key=lender_private_key,
        )
        
        result['ftct_amount'] = ftct_amount
        logger.info(f"Withdrew ~{ftct_amount} FTCT (tx: {result['tx_hash']})")
        return result
    
    # ============================================================
    # WRITE FUNCTIONS - Loans (Admin)
    # ============================================================
    
    def create_loan(
        self,
        borrower_address: str,
        amount: float,
        apr_bps: int,
        term_days: int,
        admin_private_key: Optional[str] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Create a new loan (admin only)
        
        Args:
            borrower_address: Borrower address
            amount: Loan amount in FTCT
            apr_bps: Annual percentage rate in basis points (e.g., 1200 = 12%)
            term_days: Loan term in days
            admin_private_key: Admin's private key (defaults to settings)
            
        Returns:
            Tuple of (loan_id, transaction details)
        """
        admin_key = admin_private_key or settings.ADMIN_PRIVATE_KEY
        admin_address = settings.ADMIN_ADDRESS
        
        borrower_address = self.checksum_address(borrower_address)
        amount_wei = self.to_wei(amount)
        
        logger.info(f"Creating loan: {amount} FTCT for {borrower_address}, {apr_bps}bps, {term_days}d")
        
        function = self.contract.functions.createLoan(
            borrower_address,
            amount_wei,
            apr_bps,
            term_days
        )
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=admin_address,
            private_key=admin_key,
        )
        
        # Extract loan ID from LoanCreated event
        receipt = result['receipt']
        loan_created_event = None
        
        for log in receipt['logs']:
            try:
                decoded = self.contract.events.LoanCreated().process_log(log)
                loan_created_event = decoded
                break
            except:
                continue
        
        if loan_created_event:
            loan_id = loan_created_event['args']['id']
        else:
            # Fallback: get next ID - 1
            loan_id = self.get_next_loan_id() - 1
        
        logger.info(f"Created loan ID {loan_id} (tx: {result['tx_hash']})")
        return loan_id, result
    
    def mark_funded(
        self,
        loan_id: int,
        admin_private_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark loan as funded (reserves pool funds)
        
        Args:
            loan_id: Loan ID
            admin_private_key: Admin's private key (defaults to settings)
            
        Returns:
            Transaction details
        """
        admin_key = admin_private_key or settings.ADMIN_PRIVATE_KEY
        admin_address = settings.ADMIN_ADDRESS
        
        logger.info(f"Marking loan {loan_id} as funded")
        
        function = self.contract.functions.markFunded(loan_id)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=admin_address,
            private_key=admin_key,
        )
        
        logger.info(f"Loan {loan_id} funded (tx: {result['tx_hash']})")
        return result
    
    def mark_disbursed_ftct(
        self,
        loan_id: int,
        admin_private_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Disburse FTCT to borrower
        
        Args:
            loan_id: Loan ID
            admin_private_key: Admin's private key (defaults to settings)
            
        Returns:
            Transaction details
        """
        admin_key = admin_private_key or settings.ADMIN_PRIVATE_KEY
        admin_address = settings.ADMIN_ADDRESS
        
        logger.info(f"Disbursing loan {loan_id}")
        
        function = self.contract.functions.markDisbursedFTCT(loan_id)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=admin_address,
            private_key=admin_key,
        )
        
        logger.info(f"Loan {loan_id} disbursed (tx: {result['tx_hash']})")
        return result
    
    def mark_defaulted(
        self,
        loan_id: int,
        admin_private_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark loan as defaulted
        
        Args:
            loan_id: Loan ID
            admin_private_key: Admin's private key (defaults to settings)
            
        Returns:
            Transaction details
        """
        admin_key = admin_private_key or settings.ADMIN_PRIVATE_KEY
        admin_address = settings.ADMIN_ADDRESS
        
        logger.info(f"Marking loan {loan_id} as defaulted")
        
        function = self.contract.functions.markDefaulted(loan_id)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=admin_address,
            private_key=admin_key,
        )
        
        logger.info(f"Loan {loan_id} defaulted (tx: {result['tx_hash']})")
        return result
    
    # ============================================================
    # WRITE FUNCTIONS - Loans (Borrower)
    # ============================================================
    
    def mark_repaid_ftct(
        self,
        loan_id: int,
        on_time: bool,
        amount: float,
        borrower_address: str,
        borrower_private_key: str
    ) -> Dict[str, Any]:
        """
        Repay loan with FTCT
        Note: Borrower must approve LoanSystem to spend FTCT first
        
        Args:
            loan_id: Loan ID
            on_time: Whether repayment is on time
            amount: Amount of FTCT to repay (principal + interest)
            borrower_address: Borrower address
            borrower_private_key: Borrower's private key
            
        Returns:
            Transaction details
        """
        amount_wei = self.to_wei(amount)
        
        logger.info(f"Repaying loan {loan_id} with {amount} FTCT (on_time={on_time})")
        
        function = self.contract.functions.markRepaidFTCT(loan_id, on_time, amount_wei)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=borrower_address,
            private_key=borrower_private_key,
        )
        
        logger.info(f"Loan {loan_id} repaid (tx: {result['tx_hash']})")
        return result
    
    # ============================================================
    # EVENT QUERIES
    # ============================================================
    
    def get_deposit_events(
        self,
        from_block: int = 0,
        to_block: str = 'latest',
        user: Optional[str] = None
    ):
        """Get Deposited events"""
        filters = {}
        if user:
            filters['user'] = self.checksum_address(user)
        return self.get_event_logs('Deposited', from_block, to_block, filters)
    
    def get_withdraw_events(
        self,
        from_block: int = 0,
        to_block: str = 'latest',
        user: Optional[str] = None
    ):
        """Get Withdrawn events"""
        filters = {}
        if user:
            filters['user'] = self.checksum_address(user)
        return self.get_event_logs('Withdrawn', from_block, to_block, filters)
    
    def get_loan_created_events(
        self,
        from_block: int = 0,
        to_block: str = 'latest',
        borrower: Optional[str] = None
    ):
        """Get LoanCreated events"""
        filters = {}
        if borrower:
            filters['borrower'] = self.checksum_address(borrower)
        return self.get_event_logs('LoanCreated', from_block, to_block, filters)
    
    def get_loan_repaid_events(
        self,
        from_block: int = 0,
        to_block: str = 'latest',
        borrower: Optional[str] = None
    ):
        """Get LoanRepaid events"""
        filters = {}
        if borrower:
            filters['borrower'] = self.checksum_address(borrower)
        return self.get_event_logs('LoanRepaid', from_block, to_block, filters)
    
    def get_loan_defaulted_events(
        self,
        from_block: int = 0,
        to_block: str = 'latest',
        borrower: Optional[str] = None
    ):
        """Get LoanDefaulted events"""
        filters = {}
        if borrower:
            filters['borrower'] = self.checksum_address(borrower)
        return self.get_event_logs('LoanDefaulted', from_block, to_block, filters)

