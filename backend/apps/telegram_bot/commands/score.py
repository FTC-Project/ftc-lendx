# score.py
from typing import Dict, Any, Optional

from celery import shared_task
import requests

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.commands.register import register
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.flow import reply
from backend.apps.telegram_bot.keyboards import kb_back_cancel
from backend.apps.users.models import TelegramUser
from typing import Dict, Any, Optional
from backend.apps.scoring.models import TrustScoreSnapshot

API_URL = "http://web:8000/api/v1/score/profile"

def _score_label(score: int) -> str:
    if score >= 80:
        return "👍 Excellent"
    if score >= 60:
        return "🙂 Fair"
    if score >= 40:
        return "⚠️ Poor"
    return "❌ Very Poor"


def _token_reputation(balance: float) -> str:
    if balance >= 10:
        return "🌟 Great Reputation"
    if balance >= 5:
        return "✅ Good Reputation"
    if balance >= 1:
        return "🆗 Average"
    return "⚠️ Needs Improvement"


def _format_profile(data: Dict[str, Any]) -> str:
    score = data.get("trust_score", 0)
    score_txt = f"{score}/100 ({_score_label(score)})"

    token_balance = float(data.get("token_balance", 0))
    token_txt = f"{token_balance:.2f} CTT ({_token_reputation(token_balance)})"

    eligibility_ftc = data.get("max_loan_ftc", 0)
    eligibility_zar = data.get("max_loan_zar", 0)

    factors = data.get("score_factors", {})
    strengths = factors.get("strengths", [])
    weaknesses = factors.get("weaknesses", [])

    fx_txt = ""
    if strengths:
        fx_txt += "✅ Strengths:\n"
        fx_txt += "\n".join([f"• {s}" for s in strengths]) + "\n"
    if weaknesses:
        fx_txt += "⚠️ Weaknesses:\n"
        fx_txt += "\n".join([f"• {w}" for w in weaknesses])

    return (
        "<b>📊 Credit Score</b>\n\n"
        f"<b>TrustScore:</b> {score_txt}\n"
        f"<b>Token Balance:</b> {token_txt}\n\n"
        f"<b>Loan Eligibility:</b>\n"
        f"• {eligibility_ftc:,} FTC (≈ R{eligibility_zar:,})\n\n"
        f"{fx_txt}"
    )


def kb_score_actions() -> dict:
    rows = [
        [{"text": "📈 How to Improve", "callback_data": "score:improve"}],
        [{"text": "🔹 Token Info", "callback_data": "score:tokeninfo"}],
    ]
    return kb_back_cancel(rows)


def _fetch_score_profile(user: TelegramUser) -> Optional[Dict[str, Any]]:
    """Fetch the latest TrustScoreSnapshot for a user directly from the database."""
    snapshot = user.score_snapshots.order_by("-calculated_at").first()
    if not snapshot:
        return None

    # Map database fields to expected API structure
    return {
        "trust_score": float(snapshot.trust_score),
        "risk_category": snapshot.risk_category,
        "token_balance": getattr(user, "token_balance", 0),  # adjust if you store tokens elsewhere
        "max_loan_ftc": getattr(user, "max_loan_ftc", 0),   # adjust if calculated elsewhere
        "max_loan_zar": getattr(user, "max_loan_zar", 0),   # adjust if calculated elsewhere
        "score_factors": getattr(snapshot, "factors", {}) or {},  # factors JSONField
    }


@register(
    name="score",
    aliases=["/score"],
    description="View your TrustScore and eligibility",
    permission="verified_borrower",
)
class ScoreCommand(BaseCommand):
    name = "score"
    description = "View your TrustScore"
    permission = "verified_borrower"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @staticmethod
    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)

        cb = getattr(msg, "callback_data", None)
        if cb == "score:improve":
            reply(
                msg,
                "Tips to improve your TrustScore:\n"
                "• Pay on time\n"
                "• Increase CTT tokens\n"
                "• Maintain account verification"
            )
            return

        if cb == "score:tokeninfo":
            reply(
                msg,
                "CTT tokens come from responsible repayment behavior.\n"
                "More tokens help grow your reputation and increase loan limits."
            )
            return

        try:
            user = TelegramUser.objects.get(telegram_id=msg.user_id)
        except TelegramUser.DoesNotExist:
            reply(msg, "You must register before viewing your score. Use /register.")
            return

        profile = _fetch_score_profile(user)
        if not profile:
            reply(msg, "Your score is not available yet. Please try again later.")
            return

        reply(
            msg,
            _format_profile(profile),
            kb_score_actions(),
            parse_mode="HTML",
        )

