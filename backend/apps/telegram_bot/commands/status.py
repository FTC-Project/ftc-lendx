from typing import Optional, Dict, Any
from datetime import datetime, date

from celery import shared_task

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.commands.register import register
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.flow import reply
from backend.apps.loans.models import Loan, RepaymentSchedule
from backend.apps.users.models import TelegramUser


def _fmt_money(amount: int) -> str:
    """Format integer ZAR amount as currency string."""
    return f"R{amount:,.2f}"


def _fmt_date(d) -> str:
    """Format date/datetime objects."""
    if not d:
        return "N/A"
    if isinstance(d, (datetime, date)):
        return d.strftime("%Y-%m-%d")
    return str(d)


def _status_badge(state: str) -> str:
    """Convert loan state to user-friendly badge."""
    s = (state or "").lower()
    return {
        "disbursed": "🟢 Active",
        "defaulted": "🔴 Defaulted",
        "repaid": "✅ Paid Off",
        "funded": "⏳ Funded",
        "created": "📝 Created",
        "approved": "🟡 Approved",
        "submitted": "📨 Submitted",
        "declined": "❌ Declined",
    }.get(s, "⚪ Unknown")


def _query_latest_loan(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Return user's most recent loan, regardless of state."""
    try:
        user = TelegramUser.objects.get(telegram_id=telegram_id)

        loan = Loan.objects.filter(user=user).order_by("-created_at").first()

        if not loan:
            return None

        total_repayable = loan.amount + loan.interest_portion
        remaining = total_repayable - loan.repaid_amount

        next_due = (
            RepaymentSchedule.objects.filter(
                loan=loan, status__in=["pending", "partial"]
            )
            .order_by("due_at")
            .values_list("due_at", flat=True)
            .first()
        )

        return {
            "loan_id": str(loan.id),
            "amount": loan.amount,
            "repaid_amount": loan.repaid_amount,
            "remaining_balance": remaining,
            "interest_portion": loan.interest_portion,
            "principal_portion": loan.principal_portion,
            "next_due_date": next_due,
            "due_date": loan.due_date,
            "state": loan.state,
            "apr_bps": loan.apr_bps,
            "term_days": loan.term_days,
        }
    except TelegramUser.DoesNotExist:
        return None
    except Exception as e:
        print(f"[StatusCommand] Error querying loan: {e}")
        return None


@register(
    name="status",
    aliases=["/status"],
    description="Check the status of your most recent loan",
    permission="user",
)
class StatusCommand(BaseCommand):
    """Displays the user's most recent loan information (any state)."""

    name = "status"
    description = "Check the status of your most recent loan"
    permission = "user"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)

        if not msg.user_id:
            reply(msg, "Error identifying user.")
            return

        loan = _query_latest_loan(msg.user_id)

        if not loan:
            reply(msg, "You currently do not have any loan records.")
            return

        apr = loan["apr_bps"] / 100
        txt = (
            f"<b>💼 Loan Summary</b>\n\n"
            f"<b>Loan ID:</b> <code>{loan['loan_id'][:8]}...</code>\n"
            f"<b>Principal:</b> {_fmt_money(loan['amount'])}\n"
            f"<b>Interest:</b> {_fmt_money(loan['interest_portion'])}\n"
            f"<b>Total Repayable:</b> {_fmt_money(loan['amount'] + loan['interest_portion'])}\n\n"
            f"<b>Repaid:</b> {_fmt_money(loan['repaid_amount'])}\n"
            f"<b>Remaining:</b> {_fmt_money(loan['remaining_balance'])}\n\n"
            f"<b>Term:</b> {loan['term_days']} days\n"
            f"<b>APR:</b> {apr:.2f}%\n"
            f"<b>Next Due:</b> {_fmt_date(loan['next_due_date'])}\n"
            f"<b>Final Due:</b> {_fmt_date(loan['due_date'])}\n\n"
            f"<b>Status:</b> {_status_badge(loan['state'])}"
        )

        reply(msg, txt, parse_mode="HTML")
