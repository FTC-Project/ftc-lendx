"""
Base Web3 Contract Service
Provides common functionality for interacting with smart contracts
"""

from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError
from typing import Optional, Dict, Any
from decimal import Decimal
from django.conf import settings
import logging
import json

logger = logging.getLogger(__name__)


class BaseContractService:
    """Base class for Web3 contract interactions"""
    
    def __init__(
        self,
        contract_address: str,
        abi_path: str,
        provider_url: Optional[str] = None
    ):
        """
        Initialize the contract service
        
        Args:
            contract_address: The deployed contract address
            abi_path: Path to the contract ABI JSON file
            provider_url: Optional Web3 provider URL (defaults to settings)
        """
        self.provider_url = provider_url or settings.WEB3_PROVIDER_URL
        self.web3 = Web3(Web3.HTTPProvider(self.provider_url))
        
        if not self.web3.is_connected():
            raise ConnectionError(f"Failed to connect to Web3 provider: {self.provider_url}")
        
        # Load ABI
        with open(abi_path, 'r') as f:
            abi = json.load(f)
        
        # Create contract instance
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.contract: Contract = self.web3.eth.contract(
            address=self.contract_address,
            abi=abi
        )
        
        logger.info(f"Initialized contract at {self.contract_address}")
    
    def to_wei(self, amount: float) -> int:
        """Convert token amount to wei (18 decimals)"""
        return self.web3.to_wei(amount, 'ether')
    
    def from_wei(self, amount: int) -> Decimal:
        """Convert wei to token amount (18 decimals)"""
        return Decimal(self.web3.from_wei(amount, 'ether'))
    
    def checksum_address(self, address: str) -> str:
        """Convert address to checksum format"""
        return Web3.to_checksum_address(address)
    
    def get_account_from_private_key(self, private_key: str):
        """Get account object from private key"""
        return self.web3.eth.account.from_key(private_key)
    
    def build_and_send_transaction(
        self,
        function,
        from_address: str,
        private_key: str,
        value: int = 0,
        gas_multiplier: float = 1.2,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Build, sign, and send a transaction with nonce retry logic
        
        Args:
            function: Contract function to call
            from_address: Sender address
            private_key: Sender's private key
            value: ETH/native token value to send (in wei)
            gas_multiplier: Multiplier for gas estimation (default 1.2 = 20% buffer)
            max_retries: Maximum number of retry attempts for nonce conflicts (default 3)
            
        Returns:
            Dict with transaction hash and receipt
        """
        import time
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Get account
                account = self.get_account_from_private_key(private_key)
                from_address = self.checksum_address(from_address)
                
                # Get nonce (fresh for each attempt)
                nonce = self.web3.eth.get_transaction_count(from_address, 'pending')
                
                # Estimate gas
                try:
                    estimated_gas = function.estimate_gas({'from': from_address, 'value': value})
                    gas_limit = int(estimated_gas * gas_multiplier)
                except Exception as e:
                    logger.warning(f"Gas estimation failed: {e}. Using default 500000")
                    gas_limit = 500000
                
                # Get gas price
                gas_price = self.web3.eth.gas_price
                
                # Build transaction
                transaction = function.build_transaction({
                    'from': from_address,
                    'nonce': nonce,
                    'gas': gas_limit,
                    'gasPrice': gas_price,
                    'value': value,
                    'chainId': self.web3.eth.chain_id,
                })
                
                # Sign transaction
                signed_txn = account.sign_transaction(transaction)
                
                # Send transaction
                tx_hash = self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
                logger.info(f"Transaction sent: {tx_hash.hex()}")
                
                # Wait for receipt
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                
                if receipt['status'] == 0:
                    raise Exception("Transaction failed on-chain")
                
                logger.info(f"Transaction confirmed in block {receipt['blockNumber']}")
                
                # Small delay to ensure nonce updates propagate
                time.sleep(0.5)
                
                return {
                    'tx_hash': tx_hash.hex(),
                    'receipt': receipt,
                    'gas_used': receipt['gasUsed'],
                    'block_number': receipt['blockNumber'],
                }
                
            except ValueError as e:
                # Check if it's a nonce error
                error_message = str(e).lower()
                if 'nonce' in error_message and attempt < max_retries - 1:
                    logger.warning(f"Nonce conflict detected, retrying... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(1)  # Wait before retry
                    last_error = e
                    continue
                raise
            except ContractLogicError as e:
                logger.error(f"Contract logic error: {e}")
                raise
            except Exception as e:
                # Check if it's a nonce-related error
                error_message = str(e).lower()
                if ('nonce' in error_message or 'replacement transaction underpriced' in error_message) and attempt < max_retries - 1:
                    logger.warning(f"Transaction conflict, retrying... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(1)
                    last_error = e
                    continue
                logger.error(f"Transaction error: {e}")
                raise
        
        # If we get here, all retries failed
        if last_error:
            raise last_error
        raise Exception("Transaction failed after maximum retries")
    
    def call_read_function(self, function_name: str, *args) -> Any:
        """
        Call a read-only contract function
        
        Args:
            function_name: Name of the function to call
            *args: Arguments to pass to the function
            
        Returns:
            Function result
        """
        try:
            function = getattr(self.contract.functions, function_name)
            result = function(*args).call()
            return result
        except Exception as e:
            logger.error(f"Error calling {function_name}: {e}")
            raise
    
    def get_event_logs(
        self,
        event_name: str,
        from_block: int = 0,
        to_block: str = 'latest',
        filters: Optional[Dict] = None
    ):
        """
        Get event logs from the contract
        
        Args:
            event_name: Name of the event
            from_block: Starting block number
            to_block: Ending block number or 'latest'
            filters: Optional filters for indexed parameters
            
        Returns:
            List of event logs
        """
        try:
            event = getattr(self.contract.events, event_name)
            
            filter_params = {
                'fromBlock': from_block,
                'toBlock': to_block,
            }
            
            if filters:
                filter_params['argument_filters'] = filters
            
            logs = event.get_logs(**filter_params)
            return logs
            
        except Exception as e:
            logger.error(f"Error getting {event_name} logs: {e}")
            raise
    
    def get_transaction_receipt(self, tx_hash: str):
        """Get transaction receipt"""
        return self.web3.eth.get_transaction_receipt(tx_hash)
    
    def get_block_number(self) -> int:
        """Get current block number"""
        return self.web3.eth.block_number

