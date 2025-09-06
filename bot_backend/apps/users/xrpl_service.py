import time
from dataclasses import dataclass
from typing import Optional

import requests
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo, AccountTx
from xrpl.models.transactions import Payment
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops, drops_to_xrp
from xrpl.wallet import Wallet, generate_faucet_wallet

TESTNET_RPC = "https://s.altnet.rippletest.net:51234"
TESTNET_FAUCET = "https://faucet.altnet.rippletest.net/accounts"


@dataclass
class GeneratedWallet:
    classic_address: str
    seed: str


class XRPLClient:
    """Simple sync XRPL client - no async complexity!"""

    def __init__(self):
        self.client = JsonRpcClient(TESTNET_RPC)
        print(f"🔗 XRPL client initialized: {TESTNET_RPC}")

    def get_xrp_balance(self, address: str) -> float:
        """Get XRP balance for an address - simple sync call."""
        try:
            req = AccountInfo(account=address, ledger_index="validated", strict=True)
            resp = self.client.request(req)

            if resp.is_successful():
                balance_drops = (resp.result["account_data"]["Balance"])
                balance_xrp = float(drops_to_xrp(balance_drops))
                print(f"💰 Balance for {address}: {balance_xrp} XRP")
                return balance_xrp
            else:
                print(f"❌ Failed to get balance: {resp.result}")
                return 0.0

        except Exception as e:
            print(f"❌ Error getting balance for {address}: {e}")
            return 0.0

    def send_xrp(self, sender_seed: str, destination: str, amount_xrp: float) -> Optional[str]:
        """Send XRP from one address to another - sync transaction."""
        try:
            # Create wallet from seed
            sender_wallet = Wallet.from_seed(sender_seed)
            print(f"💸 Sending {amount_xrp} XRP from {sender_wallet.classic_address} to {destination}")

            # Create payment transaction
            payment = Payment(
                account=sender_wallet.classic_address,
                destination=destination,
                amount=str(xrp_to_drops(amount_xrp)),  # Convert to drops
            )

            # Submit transaction and wait for validation
            tx_response = submit_and_wait(payment, self.client, sender_wallet)

            if tx_response.is_successful():
                tx_hash = tx_response.result.get("tx_json", {}).get("hash") or tx_response.result.get("hash")
                print(f"✅ Transaction successful! Hash: {tx_hash}")
                return tx_hash
            else:
                print(f"❌ Transaction failed: {tx_response.result}")
                return None

        except Exception as e:
            print(f"❌ Error sending XRP: {e}")
            return None

    def create_wallet(self) -> GeneratedWallet:
        """Create a new XRPL wallet - does NOT fund it."""
        try:
            wallet = Wallet.create()
            print(f"🆕 Created wallet: {wallet.classic_address}")

            return GeneratedWallet(
                classic_address=wallet.classic_address,
                seed=wallet.__getattribute__("seed")
            )

        except Exception as e:
            print(f"❌ Error creating wallet: {e}")
            raise

    def create_and_fund_wallet(self) -> Optional[GeneratedWallet]:
        """Use the old generate_faucet_wallet method - sometimes more reliable."""
        try:
            print("🚰 Using legacy faucet wallet generation...")
            wallet = generate_faucet_wallet(self.client, debug=True)

            return GeneratedWallet(
                classic_address=wallet.classic_address,
                seed=wallet.__getattribute__("seed")
            )

        except Exception as e:
            print(f"❌ Error with legacy faucet wallet: {e}")
            return None

    def get_transaction_history(self, address: str, limit: int = 10) -> list:
        """Get recent transactions for an address - useful for debugging."""
        try:
            req = AccountTx(account=address, limit=limit)
            resp = self.client.request(req)

            if resp.is_successful():
                transactions = resp.result.get("transactions", [])
                print(f"📜 Found {len(transactions)} transactions for {address}")
                return transactions
            else:
                print(f"❌ Failed to get transaction history: {resp.result}")
                return []

        except Exception as e:
            print(f"❌ Error getting transaction history: {e}")
            return []

    def wait_for_balance_update(self, address: str, expected_min_balance: float = 0, timeout: int = 30) -> float:
        """Wait for a wallet balance to update - useful after funding."""
        print(f"⏳ Waiting for balance update on {address}...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            balance = self.get_xrp_balance(address)
            if balance >= expected_min_balance:
                print(f"✅ Balance updated: {balance} XRP")
                return balance

            print(f"⏳ Current balance: {balance} XRP, waiting...")
            time.sleep(2)

        print(f"⚠️ Timeout waiting for balance update")
        return self.get_xrp_balance(address)


# Global XRPL client instance
xrpl_client = XRPLClient()


# Convenience functions the bot.
def get_balance(wallet_address: str) -> float:
    """Simple function to get XRP balance."""
    return xrpl_client.get_xrp_balance(wallet_address)


def send_xrp(sender_seed: str, recipient_address: str, amount: float) -> Optional[str]:
    """Simple function to send XRP."""
    return xrpl_client.send_xrp(sender_seed, recipient_address, amount)


def create_user_wallet() -> Optional[GeneratedWallet]:
    """Create and fund a new user wallet."""
    # Try the new method first
    wallet = xrpl_client.create_and_fund_wallet()
    return wallet
