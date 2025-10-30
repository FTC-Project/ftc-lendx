from web3 import Web3
from django.conf import settings

from backend.apps.tokens.models import CreditTrustBalance
from backend.apps.users.models import TelegramUser
from django.utils import timezone
import logging

##################################################
# This services checks the on-chain CTT balance,
# and updates the off-chain DB record if different.
##################################################
logger = logging.getLogger(__name__)


class CreditTrustSyncService:
    def __init__(self):
        self.client = CreditTrustTokenClient()

    def sync_user_balance(self, user: TelegramUser):
        """Fetch on-chain balance and update DB if different."""
        try:
            on_chain = self.client.get_balance(user.wallet.address)
            off_chain_record, _ = CreditTrustBalance.objects.get_or_create(user=user)
            if off_chain_record.balance != on_chain:
                logger.info(
                    f"Updating {user.id} balance: {off_chain_record.balance} → {on_chain}"
                )
                off_chain_record.balance = on_chain
                off_chain_record.updated_at = timezone.now()
                off_chain_record.save()
                # invalidate Redis cache if you’re using one
            return True
        except Exception as e:
            logger.error(f"Failed to sync balance for {user.id}: {e}")
            return False

    def sync_all_balances(self):
        users = TelegramUser.objects.filter(is_active=True)
        for user in users:
            self.sync_user_balance(user)


##################################################
# This service fetches the on-chain CTT balance,
# for a given address, and returns it.
##################################################
class CreditTrustTokenClient:
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER))
        self.contract = self.web3.eth.contract(
            address=settings.CREDIT_TRUST_TOKEN_ADDRESS,
            abi=settings.CREDIT_TRUST_TOKEN_ABI,
        )

    def get_balance(self, address: str) -> int:
        balance_in_wei = self.contract.functions.tokenBalance(address).call()
        return balance_in_wei / 10**18
