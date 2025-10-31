from __future__ import annotations

import os
from celery import shared_task

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register
from backend.apps.telegram_bot.flow import reply

from backend.apps.users.models import TelegramUser
from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.users.crypto import decrypt_secret
from urllib.parse import urlencode


CMD = "deposit"


def _public_deposit_url() -> str:
    base = os.getenv("PUBLIC_URL") or ""
    if not base:
        return "#"
    return f"{base.rstrip('/')}/deposit_ftct/"


def _format_pool_overview(total_pool: float, user_shares: float, user_value: float) -> str:
    return (
        "🏦 <b>Pool Overview</b>\n\n"
        f"<b>Total Pool Balance:</b> {total_pool:,.2f} FTCT\n"
        f"<b>Your Shares:</b> {user_shares:,.6f}\n"
        f"<b>Your Investment (est.):</b> {user_value:,.2f} FTCT\n\n"
        "<b>Terms</b>\n"
        "• Deposits receive pool shares proportional to contribution.\n"
        "• Share value rises with interest from funded loans.\n"
        "• Withdraw by redeeming shares for FTCT (subject to liquidity).\n"
    )


def _kb_deposit_actions(wallet: str | None = None, private_key: str | None = None) -> dict:
    base = _public_deposit_url()
    url = base
    if wallet and private_key and base != "#":
        q = urlencode({"wallet": wallet, "private_key": private_key})
        url = f"{base}?{q}"
    return {
        "inline_keyboard": [
            [
                {"text": "💸 Make a deposit", "url": url},
            ],
        ]
    }


@register(
    name=CMD,
    aliases=[f"/{CMD}"],
    description="View pool details and open deposit page",
    permission="lender",
)
class DepositCommand(BaseCommand):
    name = CMD
    description = "View pool details and open deposit page"
    permission = "lender"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)

        # Let user know we're fetching on-chain data asynchronously
        reply(
            msg,
            "⏳ Fetching pool details...",
        )

        # Offload all crypto reads to scoring queue
        fetch_and_show_pool_overview.delay(message_data)


@shared_task(queue="scoring")
def fetch_and_show_pool_overview(message_data: dict) -> None:
    """
    Scoring-queue task: fetch on-chain pool metrics and show to the lender.
    """
    msg = TelegramMessage.from_payload(message_data)

    user = TelegramUser.objects.filter(telegram_id=msg.user_id).first()
    if not user:
        reply(msg, "❌ Could not find your user account.")
        return

    if not user.is_registered or user.role != "lender":
        reply(msg, "⛔ This command is only available to registered lenders.")
        return

    if not hasattr(user, "wallet") or not user.wallet:
        reply(
            msg,
            "❌ <b>No Wallet Found</b>\n\n"
            "Please contact support to set up your wallet.",
            parse_mode="HTML",
        )
        return

    wallet_addr = user.wallet.address

    # On-chain reads
    ls = LoanSystemService()
    total_pool = float(ls.get_total_pool())
    user_shares = float(ls.get_shares_of(wallet_addr))
    user_value = float(ls.get_share_value(user_shares)) if user_shares > 0 else 0.0

    # Render overview with actions
    text = _format_pool_overview(total_pool, user_shares, user_value)
    # Include prefilled params
    private_key = None
    try:
        private_key = decrypt_secret(user.wallet.secret_encrypted)
    except Exception:
        private_key = None
    kb = _kb_deposit_actions(wallet=user.wallet.address, private_key=private_key)

    reply(
        msg,
        text,
        reply_markup=kb,
        parse_mode="HTML",
    )


