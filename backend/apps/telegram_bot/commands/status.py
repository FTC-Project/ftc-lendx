from typing import Optional, Dict, Any
from datetime import datetime, date
from asgiref.sync import async_to_sync

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.commands.register import register
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.flow import reply
from backend.apps.telegram_bot.keyboards import kb_back_cancel
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
        "declined": "❌ Declined",
    }.get(s, "⚪ Unknown")


def _kb_loan_actions(loan_id: str):
    """Inline keyboard with Make Payment / View History buttons."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("💳 Make Payment", callback_data=f"pay:{loan_id}"),
            InlineKeyboardButton("📜 View History", callback_data=f"history:{loan_id}"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="back")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def _query_active_loan(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Return user's most recent active loan."""
    try:
        user = await TelegramUser.objects.aget(telegram_id=telegram_id)

        loan = await Loan.objects.filter(user=user, state__in=["disbursed", "funded"]) \
                                 .order_by("-created_at").afirst()
        if not loan:
            return None

        total_repayable = loan.amount + loan.interest_portion
        remaining = total_repayable - loan.repaid_amount

        next_due = await RepaymentSchedule.objects.filter(
            loan=loan, status__in=["pending", "partial"]
        ).order_by("due_at").values_list("due_at", flat=True).afirst()

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
    description="Check your active loan status",
    permission="user",
)
class StatusCommand(BaseCommand):
    """Displays the user's active loan information."""

    @property
    def task(self):
        return None

    def handle(self, msg: TelegramMessage) -> None:
        if not msg.user_id:
            reply(msg, "Error identifying user.")
            return

        loan = async_to_sync(_query_active_loan)(msg.user_id)

        if not loan:
            reply(
                msg,
                "You currently do not have an active loan.\n\nUse /apply to request a new loan.",
                reply_markup=kb_back_cancel(),
            )
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

        keyboard = _kb_loan_actions(loan["loan_id"])

        # Use HTML safely; pass keyboard object to reply
        reply(msg, txt, keyboard=keyboard, parse_mode="HTML")
