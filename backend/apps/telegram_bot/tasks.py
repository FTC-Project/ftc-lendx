from __future__ import annotations

import os
import requests
from celery import shared_task
from dotenv import load_dotenv
from typing import Optional

from backend.apps.scoring.tasks import start_scoring_pipeline
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.tokens.services.credittrust_sync import CreditTrustSyncService
from backend.apps.tokens.services.ftc_token import FTCTokenService
from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.users.models import TelegramUser
from backend.apps.loans.models import Loan, Repayment, RepaymentSchedule
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(queue="telegram_bot")
def send_telegram_message_task(
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
    callback_query_id: str | None = None,
    previous_message_id: int | None = None,
    previous_inline_message_id: str | None = None,
    parse_mode: str = "Markdown",
    fsm_persist_last_msg: bool = False,
) -> bool:
    """
    1) answerCallbackQuery (stop spinner) if provided
    2) editMessageReplyMarkup with empty keyboard to remove old buttons
    3) sendMessage
    4) (optional) persist result.message_id into FSM.data['last_bot_message_id'] atomically
    """
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    api_root = "https://api.telegram.org"
    api_url = f"{api_root}/bot{token}"

    # 1) stop spinner if needed
    if callback_query_id:
        try:
            r = requests.post(
                f"{api_url}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id},
                timeout=5,
            )
            if not r.ok:
                print(
                    f"[task] Warning: answerCallbackQuery failed {r.status_code}: {r.text}"
                )
        except requests.RequestException as e:
            print(f"[task] Warning: could not answer callback query ({e})")

    # 2) clear old inline keyboard
    if previous_inline_message_id or previous_message_id:
        edit_payload = {"reply_markup": {"inline_keyboard": []}}
        if previous_inline_message_id:
            edit_payload["inline_message_id"] = previous_inline_message_id
        else:
            edit_payload["chat_id"] = chat_id
            edit_payload["message_id"] = previous_message_id
        try:
            r = requests.post(
                f"{api_url}/editMessageReplyMarkup", json=edit_payload, timeout=5
            )
            if not r.ok:
                print(
                    f"[task] Warning: editMessageReplyMarkup failed {r.status_code}: {r.text}"
                )
        except requests.RequestException as e:
            print(f"[task] Warning: could not edit reply markup ({e})")

    # 3) send new message
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(f"{api_url}/sendMessage", json=payload, timeout=10)
        resp.raise_for_status()

        # 4) persist last bot message id into FSM.data atomically
        if fsm_persist_last_msg:
            try:
                j = resp.json()
                msg_id = j.get("result", {}).get("message_id")
                if msg_id:
                    fsm = FSMStore()
                    fsm.update_data(chat_id, {"last_bot_message_id": msg_id})
            except Exception as e:
                print(f"[task] Warning: could not persist last_bot_message_id: {e}")

        return True
    except requests.RequestException as exc:
        print(f"[task] Error sending message to {chat_id}: {exc}")
        return False


@shared_task(queue="telegram_bot")
def check_permission_and_dispatch_task(
    message_data: dict,
    command_name: str,
    permission_level: str,
) -> None:
    """
    Non-blocking permission check that dispatches to command if authorized.

    This task:
    1. Checks if user has required permission (can query DB without blocking bot)
    2. If authorized, kicks off the command's task
    3. If not authorized, sends error message to user
    """
    from backend.apps.telegram_bot.messages import TelegramMessage
    from backend.apps.telegram_bot.registry import get_command_meta

    msg = TelegramMessage.from_payload(message_data)

    # Check permission
    has_permission = _check_user_permission(msg.user_id, permission_level)

    if not has_permission:
        # Send unauthorized message
        error_msg = _get_permission_error_message(permission_level)
        send_telegram_message_task.delay(msg.chat_id, error_msg)
        print(
            f"[task] User {msg.user_id} not authorized for {command_name} (requires {permission_level})"
        )
        return

    # User is authorized - get command and dispatch
    meta = get_command_meta(command_name)
    if not meta:
        print(f"[task] Unknown command '{command_name}' in dispatch")
        return

    # Instantiate command and get its task
    command_instance = meta.cls()
    if hasattr(command_instance, "task") and command_instance.task:
        # Dispatch to command's task
        command_instance.task.delay(message_data)
    else:
        print(f"[task] Command '{command_name}' has no task method")


def _check_user_permission(user_id: int, permission_level: str) -> bool:
    """
    Check if user has the required permission level.
    This runs in a Celery worker, so DB queries are non-blocking.
    """
    if permission_level == "public":
        return True

    # Import here to avoid circular imports
    from backend.apps.users.models import TelegramUser
    from backend.apps.kyc.models import KYCVerification

    try:
        user = TelegramUser.objects.filter(telegram_id=user_id).first()

        if not user:
            return False

        # Must be active (accepted TOS)
        if not user.is_active:
            return False

        # If admin, return True
        if user.role == "admin":
            return True

        if permission_level == "user":
            # Just needs to be an active user
            return True

        if permission_level == "registered":
            # Must have completed registration
            return user.is_registered

        if permission_level == "verified":
            # Must have verified KYC
            kyc = KYCVerification.objects.filter(user=user).first()
            return kyc and kyc.status == "verified"

        if permission_level == "verified_borrower":
            # Must be verified AND a borrower
            if user.role != "borrower":
                return False
            kyc = KYCVerification.objects.filter(user=user).first()
            return kyc and kyc.status == "verified" and user.is_registered

        if permission_level == "verified_lender":
            # Must be verified AND a lender
            if user.role != "lender":
                return False
            kyc = KYCVerification.objects.filter(user=user).first()
            return kyc and kyc.status == "verified" and user.is_registered

        if permission_level == "borrower":
            # Must be registered borrower
            return user.is_registered and user.role == "borrower"

        if permission_level == "lender":
            # Must be registered lender
            return user.is_registered and user.role == "lender"

        if permission_level == "admin":
            # Must be admin
            return user.is_registered and user.role == "admin"

        # Unknown permission level - deny by default
        print(f"[task] Unknown permission level: {permission_level}")
        return False

    except Exception as e:
        print(f"[task] Error checking permission for user {user_id}: {e}")
        return False


def _get_permission_error_message(permission_level: str) -> str:
    """Get appropriate error message for permission denial."""
    messages = {
        "user": "⛔ You need to accept the Terms of Service first. Use /start to get started.",
        "registered": "⛔ You need to complete registration first. Use /register to get started.",
        "verified": "⛔ You need to complete KYC verification first. Use /register to get started.",
        "verified_borrower": "⛔ This command is only available to verified borrowers. Please complete registration and KYC verification.",
        "verified_lender": "⛔ This command is only available to verified lenders. Please complete registration and KYC verification.",
        "borrower": "⛔ This command is only available to borrowers.",
        "lender": "⛔ This command is only available to lenders.",
        "admin": "⛔ This command is only available to administrators.",
    }
    return messages.get(
        permission_level, "⛔ You don't have permission to use this command."
    )

# 2 Minute max
@shared_task(queue="scoring", task_time_limit=120)
def process_loan_onchain(loan_id: str) -> None:
    """
    Process loan creation on-chain asynchronously with retry logic.

    This task:
    1. Creates the loan on-chain
    2. Marks it as funded
    3. Disburses funds to the borrower
    4. Updates the loan state in the database
    5. Notifies the user of success or failure

    Args:
        loan_id: UUID of the loan to process
        chat_id: Telegram chat ID to send notifications to
    """
    import logging
    from backend.apps.loans.models import Loan
    from backend.apps.tokens.services.loan_system import LoanSystemService
    from backend.apps.users.models import Notification

    logger = logging.getLogger(__name__)

    try:
        logger.info(f"[OnChain] Processing loan {loan_id}")

        # Get the loan
        loan = Loan.objects.get(id=loan_id)
        if not loan:
            logger.error(f"[OnChain] Loan {loan_id} not found")
            return
        user = loan.user
        chat_id = user.telegram_id

        # Check if user has a wallet
        if not hasattr(user, "wallet") or not user.wallet:
            error_msg = (
                "❌ <b>On-Chain Processing Failed</b>\n\n"
                f"<b>Loan ID:</b> <code>{str(loan.id)[:8]}...</code>\n\n"
                "You don't have a wallet configured. Please contact support."
            )
            send_telegram_message_task.delay(
                chat_id=chat_id, text=error_msg, parse_mode="HTML"
            )
            loan.state = "declined"
            loan.save(update_fields=["state"])
            return

        loan_system = LoanSystemService()

        # Step 1: Create loan on-chain
        logger.info(
            f"[OnChain] Creating loan on-chain: {loan.amount} FTC, {loan.apr_bps}bps, {loan.term_days}d"
        )
        onchain_loan_id, create_result = loan_system.create_loan(
            borrower_address=user.wallet.address,
            amount=loan.amount,
            apr_bps=loan.apr_bps,
            term_days=loan.term_days,
        )
        logger.info(
            f"[OnChain] Created loan with on-chain ID {onchain_loan_id}, tx: {create_result['tx_hash']}"
        )

        # Update loan with on-chain ID
        loan.onchain_loan_id = onchain_loan_id
        loan.save(update_fields=["onchain_loan_id"])

        # Create notification
        Notification.objects.create(
            user=user,
            kind="loan_created_on_chain",
            payload={
                "loan_id": onchain_loan_id,
                "amount": loan.amount,
                "apr_bps": loan.apr_bps,
                "term_days": loan.term_days,
                "tx_hash": create_result["tx_hash"],
            },
        )

        # Step 2: Mark as funded
        logger.info(f"[OnChain] Marking loan {onchain_loan_id} as funded")
        fund_result = loan_system.mark_funded(onchain_loan_id)
        logger.info(
            f"[OnChain] Funded loan {onchain_loan_id}, tx: {fund_result['tx_hash']}"
        )

        Notification.objects.create(
            user=user,
            kind="loan_funded_on_chain",
            payload={
                "loan_id": onchain_loan_id,
                "amount": loan.amount,
                "apr_bps": loan.apr_bps,
                "term_days": loan.term_days,
                "tx_hash": fund_result["tx_hash"],
            },
        )

        # Step 3: Disburse to borrower
        logger.info(f"[OnChain] Disbursing loan {onchain_loan_id} to borrower")
        disburse_result = loan_system.mark_disbursed_ftct(onchain_loan_id)
        logger.info(
            f"[OnChain] Disbursed loan {onchain_loan_id}, tx: {disburse_result['tx_hash']}"
        )

        Notification.objects.create(
            user=user,
            kind="loan_disbursed_on_chain",
            payload={
                "loan_id": onchain_loan_id,
                "amount": loan.amount,
                "apr_bps": loan.apr_bps,
                "term_days": loan.term_days,
                "tx_hash": disburse_result["tx_hash"],
            },
        )

        # Step 4: Update loan state to disbursed
        loan.state = "disbursed"
        loan.save(update_fields=["state"])

        # Send success message to user
        success_msg = (
            "🎉 <b>Loan Approved & Funded!</b>\n\n"
            f"<b>Loan ID:</b> <code>{str(loan.id)[:8]}...</code>\n"
            f"<b>On-Chain ID:</b> {onchain_loan_id}\n\n"
            f"<b>Amount:</b> R{loan.amount:,}\n"
            f"<b>Term:</b> {loan.term_days} days\n"
            f"<b>Interest Rate:</b> {loan.apr_bps / 100:.2f}%\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>R{loan.amount:,} FTC</b> has been deposited to your wallet!\n\n"
            f"<b>Transactions:</b>\n"
            f"1️⃣ Create: <code>{create_result['tx_hash'][:16]}...</code>\n"
            f"2️⃣ Fund: <code>{fund_result['tx_hash'][:16]}...</code>\n"
            f"3️⃣ Disburse: <code>{disburse_result['tx_hash'][:16]}...</code>\n\n"
            "<i>Use /balance to check your wallet balance.</i>"
        )

        send_telegram_message_task.delay(
            chat_id=chat_id, text=success_msg, parse_mode="HTML"
        )

        logger.info(f"[OnChain] Successfully processed loan {loan.id}")

    except Loan.DoesNotExist:
        logger.error(f"[OnChain] Loan {loan_id} not found")
        error_msg = (
            "❌ <b>On-Chain Processing Failed</b>\n\n"
            "Loan not found in database. Please contact support."
        )
        send_telegram_message_task.delay(
            chat_id=chat_id, text=error_msg, parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"[OnChain] Error processing loan {loan_id}: {e}", exc_info=True)
        try:
            loan = Loan.objects.get(id=loan_id)
            loan.state = "declined"
            loan.save(update_fields=["state"])
        except:
            pass

        error_msg = (
            "❌ <b>On-Chain Processing Failed</b>\n\n"
            f"<b>Loan ID:</b> <code>{str(loan_id)[:8]}...</code>\n\n"
            "We encountered an error while processing your loan on the blockchain.\n\n"
            f"<i>Error: {str(e)}</i>\n\n"
            "Your application has been cancelled. Please try again later or contact support."
        )

        send_telegram_message_task.delay(
            chat_id=chat_id, text=error_msg, parse_mode="HTML"
        )


def _fmt_ftc(amount: float) -> str:
    """Format FTC amount."""
    return f"{amount:,.8f} FTC" # Increased precision for display


@shared_task(queue="scoring", task_time_limit=240)
def process_repayment_onchain(
    loan_id,
    user_id,
    chat_id,
    wallet_address,
    user_private_key,
    ftc_amount: float, # Explicitly expect float
    is_on_time,
):
    from backend.apps.telegram_bot.tasks import send_telegram_message_task
    try:
        loan = Loan.objects.get(id=loan_id)
        user = TelegramUser.objects.get(id=user_id)
        ftc_service = FTCTokenService()
        loan_service = LoanSystemService()
        
        # Ensure ftc_amount is a float
        ftc_amount_float = float(ftc_amount)

        # Step 1: Approve LoanSystem to spend FTC
        # ftc_amount_float passed to the approve service
        approve_result = ftc_service.approve(
            owner_address=wallet_address,
            spender_address=settings.LOANSYSTEM_ADDRESS,
            amount=ftc_amount_float + 0.1,
            private_key=user_private_key,
        )
        logger.info(f"[RepayTask] Approved: {approve_result['tx_hash']}")

        # Step 2: Repay on chain
        # ftc_amount_float passed to the repay service
        repay_result = loan_service.mark_repaid_ftct(
            loan_id=loan.onchain_loan_id,
            on_time=is_on_time,
            amount=ftc_amount_float + 0.1,
            borrower_address=wallet_address,
            borrower_private_key=user_private_key,
        )
        logger.info(f"[RepayTask] Repaid on-chain: {repay_result['tx_hash']}")

        # Get schedule object, ensuring amounts are treated as float for comparison
        schedule = RepaymentSchedule.objects.filter(loan=loan, installment_no=1).first()
        
        # Update loan schedule
        schedule.amount_paid = float(schedule.amount_paid) + ftc_amount_float
        schedule.status = "paid" if schedule.amount_paid >= float(schedule.amount_due) else "partial"
        schedule.save(update_fields=["amount_paid", "status"])
        
        # Update Repayment object
        Repayment.objects.create(
            loan=loan,
            amount=ftc_amount_float, # Use float amount
            schedule=schedule,
            tx_hash=repay_result["tx_hash"],
        )
        
        # Update loan itself to be paid - using the precise float amount
        loan.state = "repaid"
        loan.repaid_amount = ftc_amount_float
        
        # The true ZAR interest portion is the total repaid amount minus the principal
        loan.interest_portion = ftc_amount_float - float(loan.amount)
        loan.save(update_fields=["state", "repaid_amount", "interest_portion"])
        
        # Now execute the sync credit trust balance task
        credit_trust_sync = CreditTrustSyncService()
        credit_trust_sync.sync_user_balance(user)
        
        # Now execute the score update task
        start_scoring_pipeline.delay(user_id=user.id)

        msg = (
            "✅ <b>Repayment Complete</b>\n\n"
            f"Loan: <code>{str(loan.id)[:8]}...</code>\n"
            f"FTC Amount: {_fmt_ftc(ftc_amount_float)}\n\n" # Display as precise float
            f"1️⃣ Approve: <code>{approve_result['tx_hash'][:16]}...</code>\n"
            f"2️⃣ Repay: <code>{repay_result['tx_hash'][:16]}...</code>\n"
            "\n<i>Thank you for your repayment! Use /status to check your loan record.</i>"
        )
        send_telegram_message_task.delay(chat_id=chat_id, text=msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"[RepayTask] Error during on-chain repayment of loan {loan_id}: {e}", exc_info=True)
        err_msg = (
            "❌ <b>Repayment Failed</b>\n\n"
            f"Loan: <code>{str(loan_id)[:8]}...</code>\n\n"
            f"Error: {str(e)}\n\n"
            "Please try again or contact support if the issue persists."
        )
        send_telegram_message_task.delay(chat_id=chat_id, text=err_msg, parse_mode="HTML")