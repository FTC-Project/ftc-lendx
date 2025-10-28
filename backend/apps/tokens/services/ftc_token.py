"""
FTCToken (ERC20) Contract Service
Handles minting, burning, transfers, approvals, and balance queries
"""

from typing import Optional, Dict, Any
from decimal import Decimal
from django.conf import settings
import logging
from .base_contract import BaseContractService

logger = logging.getLogger(__name__)


class FTCTokenService(BaseContractService):
    """Service for interacting with the FTCToken contract"""
    
    def __init__(self):
        super().__init__(
            contract_address=settings.FTCTOKEN_ADDRESS,
            abi_path=settings.FTCTOKEN_ABI_PATH,
        )
    
    # ============================================================
    # READ-ONLY FUNCTIONS
    # ============================================================
    
    def get_balance(self, address: str) -> Decimal:
        """
        Get FTCT balance of an address
        
        Args:
            address: Wallet address
            
        Returns:
            Balance in FTCT (Decimal)
        """
        address = self.checksum_address(address)
        balance_wei = self.call_read_function('balanceOf', address)
        return self.from_wei(balance_wei)
    
    def get_total_supply(self) -> Decimal:
        """Get total supply of FTCT tokens"""
        supply_wei = self.call_read_function('totalSupply')
        return self.from_wei(supply_wei)
    
    def get_allowance(self, owner: str, spender: str) -> Decimal:
        """
        Get approved allowance
        
        Args:
            owner: Token owner address
            spender: Spender address
            
        Returns:
            Allowance in FTCT (Decimal)
        """
        owner = self.checksum_address(owner)
        spender = self.checksum_address(spender)
        allowance_wei = self.call_read_function('allowance', owner, spender)
        return self.from_wei(allowance_wei)
    
    def get_owner(self) -> str:
        """Get the contract owner (who can mint)"""
        return self.call_read_function('owner')
    
    def get_token_info(self) -> Dict[str, Any]:
        """Get token name, symbol, and decimals"""
        return {
            'name': self.call_read_function('name'),
            'symbol': self.call_read_function('symbol'),
            'decimals': self.call_read_function('decimals'),
        }
    
    # ============================================================
    # WRITE FUNCTIONS (Admin - Minting)
    # ============================================================
    
    def mint(
        self,
        to_address: str,
        amount: float,
        admin_private_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mint new tokens to an address (admin only)
        
        Args:
            to_address: Recipient address
            amount: Amount of FTCT to mint
            admin_private_key: Admin's private key (defaults to settings)
            
        Returns:
            Transaction details
        """
        admin_key = admin_private_key or settings.ADMIN_PRIVATE_KEY
        admin_address = settings.ADMIN_ADDRESS
        
        to_address = self.checksum_address(to_address)
        amount_wei = self.to_wei(amount)
        
        logger.info(f"Minting {amount} FTCT to {to_address}")
        
        function = self.contract.functions.mint(to_address, amount_wei)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=admin_address,
            private_key=admin_key,
        )
        
        logger.info(f"Minted {amount} FTCT to {to_address} (tx: {result['tx_hash']})")
        return result
    
    # ============================================================
    # WRITE FUNCTIONS (User - Transfers & Approvals)
    # ============================================================
    
    def transfer(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        private_key: str
    ) -> Dict[str, Any]:
        """
        Transfer tokens from one address to another
        
        Args:
            from_address: Sender address
            to_address: Recipient address
            amount: Amount of FTCT to transfer
            private_key: Sender's private key
            
        Returns:
            Transaction details
        """
        to_address = self.checksum_address(to_address)
        amount_wei = self.to_wei(amount)
        
        logger.info(f"Transferring {amount} FTCT from {from_address} to {to_address}")
        
        function = self.contract.functions.transfer(to_address, amount_wei)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=from_address,
            private_key=private_key,
        )
        
        logger.info(f"Transferred {amount} FTCT (tx: {result['tx_hash']})")
        return result
    
    def approve(
        self,
        owner_address: str,
        spender_address: str,
        amount: float,
        private_key: str
    ) -> Dict[str, Any]:
        """
        Approve spender to spend tokens on behalf of owner
        
        Args:
            owner_address: Token owner address
            spender_address: Address allowed to spend tokens
            amount: Amount of FTCT to approve
            private_key: Owner's private key
            
        Returns:
            Transaction details
        """
        spender_address = self.checksum_address(spender_address)
        amount_wei = self.to_wei(amount)
        
        logger.info(f"Approving {spender_address} to spend {amount} FTCT")
        
        function = self.contract.functions.approve(spender_address, amount_wei)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=owner_address,
            private_key=private_key,
        )
        
        logger.info(f"Approved {amount} FTCT for {spender_address} (tx: {result['tx_hash']})")
        return result
    
    def transfer_from(
        self,
        spender_address: str,
        from_address: str,
        to_address: str,
        amount: float,
        spender_private_key: str
    ) -> Dict[str, Any]:
        """
        Transfer tokens on behalf of another address (requires approval)
        
        Args:
            spender_address: Address executing the transfer
            from_address: Token owner address
            to_address: Recipient address
            amount: Amount of FTCT to transfer
            spender_private_key: Spender's private key
            
        Returns:
            Transaction details
        """
        from_address = self.checksum_address(from_address)
        to_address = self.checksum_address(to_address)
        amount_wei = self.to_wei(amount)
        
        logger.info(f"TransferFrom: {amount} FTCT from {from_address} to {to_address}")
        
        function = self.contract.functions.transferFrom(from_address, to_address, amount_wei)
        
        result = self.build_and_send_transaction(
            function=function,
            from_address=spender_address,
            private_key=spender_private_key,
        )
        
        logger.info(f"TransferFrom completed (tx: {result['tx_hash']})")
        return result
    
    # ============================================================
    # EVENT QUERIES
    # ============================================================
    
    def get_transfer_events(
        self,
        from_block: int = 0,
        to_block: str = 'latest',
        from_address: Optional[str] = None,
        to_address: Optional[str] = None
    ):
        """
        Get Transfer events
        
        Args:
            from_block: Starting block
            to_block: Ending block
            from_address: Filter by sender (optional)
            to_address: Filter by recipient (optional)
            
        Returns:
            List of Transfer events
        """
        filters = {}
        if from_address:
            filters['from'] = self.checksum_address(from_address)
        if to_address:
            filters['to'] = self.checksum_address(to_address)
        
        return self.get_event_logs('Transfer', from_block, to_block, filters)
    
    def get_approval_events(
        self,
        from_block: int = 0,
        to_block: str = 'latest',
        owner: Optional[str] = None,
        spender: Optional[str] = None
    ):
        """
        Get Approval events
        
        Args:
            from_block: Starting block
            to_block: Ending block
            owner: Filter by owner (optional)
            spender: Filter by spender (optional)
            
        Returns:
            List of Approval events
        """
        filters = {}
        if owner:
            filters['owner'] = self.checksum_address(owner)
        if spender:
            filters['spender'] = self.checksum_address(spender)
        
        return self.get_event_logs('Approval', from_block, to_block, filters)

