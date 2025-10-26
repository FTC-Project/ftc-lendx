from typing import List, Dict, Any
from datetime import datetime, date
from asgiref.sync import async_to_sync

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.commands.register import register
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.flow import reply
from backend.apps.telegram_bot.keyboards import kb_back_cancel
from backend.apps.loans.models import Loan
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
        "repaid": "✅ Repaid",
        "defaulted": "🔴 Defaulted",
        "disbursed": "🟢 Active",
        "funded": "⏳ Funded",
        "created": "📝 Created",
        "declined": "❌ Declined",
    }.get(s, "⚪ Unknown")


async def _query_loan_history(telegram_id: int) -> List[Dict[str, Any]]:
    """
    Return user's loan history sorted by most recent first.
    Returns all loans regardless of state.
    """
    try:
        user = await TelegramUser.objects.aget(telegram_id=telegram_id)

        loans = await Loan.objects.filter(user=user).order_by("-created_at").all()

        if not loans:
            return []

        history = []
        async for loan in loans:
            # Determine completion date based on state
            completed_at = None
            if loan.state == "repaid":
                # Get the last repayment date
                from backend.apps.loans.models import Repayment

                last_repayment = (
                    await Repayment.objects.filter(loan=loan)
                    .order_by("-received_at")
                    .values_list("received_at", flat=True)
                    .afirst()
                )
                completed_at = last_repayment
            elif loan.state == "defaulted":
                # For defaulted loans, use due_date + grace_days as approximation
                if loan.due_date:
                    from datetime import timedelta

                    completed_at = loan.due_date + timedelta(days=loan.grace_days)

            history.append(
                {
                    "loan_id": str(loan.id),
                    "amount": loan.amount,
                    "term_days": loan.term_days,
                    "state": loan.state,
                    "created_at": loan.created_at,
                    "completed_at": completed_at,
                    "apr_bps": loan.apr_bps,
                    "repaid_amount": loan.repaid_amount,
                    "total_repayable": loan.amount + loan.interest_portion,
                }
            )

        return history

    except TelegramUser.DoesNotExist:
        return []
    except Exception as e:
        print(f"[HistoryCommand] Error querying loan history: {e}")
        return []


def _format_loan_entry(loan: Dict[str, Any], index: int) -> str:
    """Format a single loan entry for display."""
    apr = loan["apr_bps"] / 100

    entry = (
        f"<b>#{index + 1} - {_status_badge(loan['state'])}</b>\n"
        f"<b>Loan ID:</b> <code>{loan['loan_id'][:8]}...</code>\n"
        f"<b>Amount:</b> {_fmt_money(loan['amount'])}\n"
        f"<b>Term:</b> {loan['term_days']} days | <b>APR:</b> {apr:.2f}%\n"
        f"<b>Created:</b> {_fmt_date(loan['created_at'])}\n"
    )

    # Add completion date if applicable
    if loan["completed_at"]:
        entry += f"<b>Completed:</b> {_fmt_date(loan['completed_at'])}\n"

    # Add payment info for completed loans
    if loan["state"] in ["repaid", "defaulted"]:
        entry += (
            f"<b>Repaid:</b> {_fmt_money(loan['repaid_amount'])} / "
            f"{_fmt_money(loan['total_repayable'])}\n"
        )

    return entry


@register(
    name="history",
    aliases=["/history"],
    description="View your loan history",
    permission="user",
)
class HistoryCommand(BaseCommand):
    """
    Displays the user's complete loan history.

    User Story: View Loan History
    Epic: Epic 3 - Loan Management
    """

    @property
    def task(self):
        return None

    def handle(self, msg: TelegramMessage) -> None:
        if not msg.user_id:
            reply(msg, "Error identifying user.")
            return

        history = async_to_sync(_query_loan_history)(msg.user_id)

        # Edge case: No loan history
        if not history:
            reply(
                msg,
                "📋 <b>Loan History</b>\n\n"
                "You don't have any loan history yet.\n\n"
                "Use /apply to request your first loan!",
                reply_markup=kb_back_cancel(),
                parse_mode="HTML",
            )
            return

        # Build history message
        header = f"📋 <b>Loan History</b>\n\n<i>Showing {len(history)} loan(s)</i>\n\n"

        # Format each loan entry with separator
        entries = []
        for idx, loan in enumerate(history):
            entries.append(_format_loan_entry(loan, idx))

        # Join with separators
        txt = header + "\n➖➖➖➖➖➖➖➖➖\n\n".join(entries)

        # Telegram message limit is 4096 characters
        # If message is too long, truncate and add note
        if len(txt) > 4000:
            # Show only first 5 loans
            entries = []
            for idx, loan in enumerate(history[:5]):
                entries.append(_format_loan_entry(loan, idx))

            txt = (
                header
                + "\n➖➖➖➖➖➖➖➖➖\n\n".join(entries)
                + f"\n\n<i>... and {len(history) - 5} more loan(s)</i>"
            )

        reply(msg, txt, reply_markup=kb_back_cancel(), parse_mode="HTML")
