from __future__ import annotations

from celery import shared_task

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.flow import reply, mark_prev_keyboard

from backend.apps.users.models import TelegramUser
from backend.apps.users.crypto import decrypt_secret
from backend.apps.tokens.services.ftc_token import FTCTokenService
from backend.apps.tokens.services.loan_system import LoanSystemService
from django.conf import settings

import logging

logger = logging.getLogger(__name__)

# -------- Command config --------
CMD = "testdeposit"


@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="[TEST] Mint FTC and deposit into pool",
    permission="public",  # For testing, anyone can use
)
class TestDepositCommand(BaseCommand):
    """Test command: Mints FTC to user and deposits into pool."""

    name = CMD
    description = "[TEST] Mint FTC and deposit into pool"
    permission = "public"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        data = {}

        try:
            # Get user and wallet
            user = TelegramUser.objects.get(telegram_id=msg.user_id)

            if not hasattr(user, "wallet") or not user.wallet:
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ <b>No Wallet Found</b>\n\n"
                    "You don't have a wallet yet. Please complete registration first.",
                    data=data,
                    parse_mode="HTML",
                )
                return

            wallet_address = user.wallet.address

            # Decrypt user's private key
            try:
                user_private_key = decrypt_secret(user.wallet.secret_encrypted)
            except Exception as e:
                logger.error(
                    f"Failed to decrypt wallet for user {user.telegram_id}: {e}"
                )
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    "❌ <b>Wallet Error</b>\n\n"
                    "Could not decrypt your wallet. Please contact support.",
                    data=data,
                    parse_mode="HTML",
                )
                return

            # Amount to mint and deposit
            amount = 1000.0  # 1000 FTC

            mark_prev_keyboard(data, msg)
            reply(
                msg,
                f"🔄 <b>Starting Test Deposit</b>\n\n"
                f"Wallet: <code>{wallet_address}</code>\n"
                f"Amount: {amount:,.2f} FTC\n\n"
                f"<i>Please wait while we process...</i>",
                data=data,
                parse_mode="HTML",
            )

            # Initialize services
            ftc_service = FTCTokenService()
            loan_service = LoanSystemService()

            try:
                # STEP 0: Send XRP for gas fees (if user has no balance)
                user_xrp_balance = ftc_service.web3.eth.get_balance(wallet_address)
                if True:
                    logger.info(
                        f"[TestDeposit] Sending gas money (XRP) to {wallet_address}"
                    )
                    admin_account = ftc_service.get_account_from_private_key(
                        settings.ADMIN_PRIVATE_KEY
                    )

                    # Send 0.1 XRP for gas
                    gas_amount = ftc_service.web3.to_wei(2, "ether")
                    tx = {
                        "from": settings.ADMIN_ADDRESS,
                        "to": wallet_address,
                        "value": gas_amount,
                        "gas": 21000,
                        "gasPrice": ftc_service.web3.eth.gas_price,
                        "nonce": ftc_service.web3.eth.get_transaction_count(
                            settings.ADMIN_ADDRESS
                        ),
                        "chainId": ftc_service.web3.eth.chain_id,
                    }
                    signed_tx = admin_account.sign_transaction(tx)
                    tx_hash = ftc_service.web3.eth.send_raw_transaction(
                        signed_tx.raw_transaction
                    )
                    ftc_service.web3.eth.wait_for_transaction_receipt(
                        tx_hash, timeout=120
                    )
                    logger.info(f"[TestDeposit] Sent gas: {tx_hash.hex()}")

                # STEP 1: Admin mints FTC to user's wallet
                logger.info(f"[TestDeposit] Minting {amount} FTC to {wallet_address}")
                mint_result = ftc_service.mint(
                    to_address=wallet_address,
                    amount=amount,
                )
                logger.info(f"[TestDeposit] Minted: {mint_result['tx_hash']}")

                # STEP 2: User approves LoanSystem to spend FTC
                logger.info(f"[TestDeposit] Approving LoanSystem to spend {amount} FTC")
                approve_result = ftc_service.approve(
                    owner_address=wallet_address,
                    spender_address=settings.LOANSYSTEM_ADDRESS,
                    amount=amount,
                    private_key=user_private_key,
                )
                logger.info(f"[TestDeposit] Approved: {approve_result['tx_hash']}")

                # STEP 3: User deposits into pool
                logger.info(f"[TestDeposit] Depositing {amount} FTC into pool")
                deposit_result = loan_service.deposit_ftct(
                    lender_address=wallet_address,
                    amount=amount - 10,
                    lender_private_key=user_private_key,
                )
                logger.info(f"[TestDeposit] Deposited: {deposit_result['tx_hash']}")

                # Get updated balances
                ftc_balance = ftc_service.get_balance(wallet_address)
                xrp_balance = ftc_service.web3.from_wei(
                    ftc_service.web3.eth.get_balance(wallet_address), "ether"
                )
                pool_shares = loan_service.get_shares_of(wallet_address)
                total_pool = loan_service.get_total_pool()

                # Success message
                success_message = (
                    f"✅ <b>Test Deposit Complete!</b>\n\n"
                    f"<b>Wallet:</b> <code>{wallet_address}</code>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"<b>Transactions:</b>\n"
                    f"0️⃣ Gas Funding: ✅ (sent 0.1 XRP for gas)\n"
                    f"1️⃣ Mint: <code>{mint_result['tx_hash'][:16]}...</code>\n"
                    f"2️⃣ Approve: <code>{approve_result['tx_hash'][:16]}...</code>\n"
                    f"3️⃣ Deposit: <code>{deposit_result['tx_hash'][:16]}...</code>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"<b>Your Balances:</b>\n"
                    f"⛽ XRP (gas): {xrp_balance:.4f} XRP\n"
                    f"💵 FTC: {ftc_balance:,.2f} FTC\n"
                    f"📊 Pool Shares: {pool_shares:,.2f}\n\n"
                    f"<b>Total Pool:</b> {total_pool:,.2f} FTC\n\n"
                    f"<i>You've successfully deposited {amount:,.2f} FTC into the lending pool!</i>"
                )

                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    success_message,
                    data=data,
                    parse_mode="HTML",
                )

            except Exception as e:
                logger.error(
                    f"[TestDeposit] Error during deposit flow: {e}", exc_info=True
                )
                mark_prev_keyboard(data, msg)
                reply(
                    msg,
                    f"❌ <b>Deposit Failed</b>\n\n"
                    f"Something went wrong during the deposit process.\n\n"
                    f"<i>Error: {str(e)}</i>\n\n"
                    f"Make sure your local blockchain is running!",
                    data=data,
                    parse_mode="HTML",
                )

        except TelegramUser.DoesNotExist:
            logger.error(f"User not found: {msg.user_id}")
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "❌ <b>User Not Found</b>\n\n" "Please register first using /start",
                data=data,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Unexpected error in testdeposit command: {e}", exc_info=True)
            mark_prev_keyboard(data, msg)
            reply(
                msg,
                "❌ <b>An Error Occurred</b>\n\n"
                "Something went wrong. Please try again later.",
                data=data,
                parse_mode="HTML",
            )
