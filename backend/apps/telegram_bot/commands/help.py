from __future__ import annotations

# NOTE (SANANA): Import statement had some redundancy
# from typing import Dict, Optional, List, Dict as DictType
from typing import Dict, Optional, List
from celery import shared_task

from backend.apps.telegram_bot.commands.base import BaseCommand
from backend.apps.telegram_bot.flow import (
    start_flow,
    clear_flow,
    mark_prev_keyboard,
    reply,
)
from backend.apps.telegram_bot.fsm_store import FSMStore
from backend.apps.telegram_bot.messages import TelegramMessage
from backend.apps.telegram_bot.registry import register

# Command + steps
CMD = "help"

S_MENU = "menu"
S_CAT_FTC = "cat_ftc"
S_CAT_FEES = "cat_fees"
S_CAT_LOAN = "cat_loan"
S_CAT_REPAY = "cat_repay"
S_CAT_SCORE = "cat_score"
S_CAT_GENERAL = "cat_general"

# Callback prefixes
CB_MENU = "help:menu"
CB_CAT = "help:cat:"
CB_Q = "help:q:"

# Category keys
CAT_FTC = "ftc"
CAT_FEES = "fees"
CAT_LOAN = "loan"
CAT_REPAY = "repay"
CAT_SCORE = "score"
CAT_GENERAL = "general"


# ---------------------------
# Keyboards (kept local to command to avoid mixing global flow callbacks)
# ---------------------------


# NOTE (SANANA): We had `def _kb(inline_rows: List[List[DictType]]) -> dict:` but changed to DICT
def _kb(inline_rows: List[List[Dict]]) -> dict:
    return {"inline_keyboard": inline_rows}


def kb_help_menu() -> dict:
    # NOTE (SANANA): The Notion help menu only has 4 categories but it makes more sense to have all these
    rows = [
        [{"text": "💳 Loan Application", "callback_data": f"{CB_CAT}{CAT_LOAN}"}],
        [{"text": "💰 FTCoin & Stablecoin", "callback_data": f"{CB_CAT}{CAT_FTC}"}],
        [{"text": "🧾 Repayment", "callback_data": f"{CB_CAT}{CAT_REPAY}"}],
        [{"text": "📈 Credit Score", "callback_data": f"{CB_CAT}{CAT_SCORE}"}],
        [{"text": "❓ General Questions", "callback_data": f"{CB_CAT}{CAT_GENERAL}"}],
        [{"text": "💸 Fees & Charges", "callback_data": f"{CB_CAT}{CAT_FEES}"}],
        [{"text": "❌ Cancel/Close ", "callback_data": "flow:cancel"}],
    ]
    return _kb(rows)

    # NOTE FROM (SANANA): All the above appear to have corresponding functions/responses except Loan which has subcategories which need to be create (done in this fix)


def kb_back_to_menu() -> dict:
    return _kb([[{"text": "⬅️ Back to Help Menu", "callback_data": CB_MENU}]])


def kb_ftc() -> dict:
    rows = [
        [{"text": "How do I get FTCoin?", "callback_data": f"{CB_Q}ftc:get"}],
        [{"text": "Is FTCoin safe?", "callback_data": f"{CB_Q}ftc:safe"}],
        [{"text": "⬅️ Back to Help Menu", "callback_data": CB_MENU}],
    ]
    return _kb(rows)


def kb_fees() -> dict:
    rows = [
        [{"text": "How to avoid late fees", "callback_data": f"{CB_Q}fees:avoid"}],
        [{"text": "Why interest rates vary", "callback_data": f"{CB_Q}fees:why"}],
        [{"text": "⬅️ Back to Help Menu", "callback_data": CB_MENU}],
    ]
    return _kb(rows)


# NOTE FROM (SANANA): So, if the user selects [Loan Application] these are the options that come up
def kb_loan() -> dict:
    rows = [
        [{"text": "How to apply", "callback_data": f"{CB_Q}loan:howtoapply"}],
        [
            {
                "text": "Why my application failed",
                "callback_data": f"{CB_Q}loan:whyfailed",
            }
        ],
        [{"text": "Document requirements", "callback_data": f"{CB_Q}loan:docs"}],
        [{"text": "⬅️ Back to Help Menu", "callback_data": CB_MENU}],
    ]
    return _kb(rows)


# (Optional simple back menus for other categories)
def kb_simple_back() -> dict:
    return kb_back_to_menu()


# ---------------------------
# Content renderers
# ---------------------------


def intro_header() -> str:
    return "🤝 *Nkadime Help Center*\n\n" "What do you need help with?"


def available_commands() -> str:
    # Short list
    return (
        "📋 *Available Commands*\n"
        "/start, /register, /linkbank, /apply, /status, /repay, /score, /tokens, /help"
    )


def render_ftc_category() -> str:
    return (
        "💰 *About FTCoin*\n\n"
        "FTCoin (FTC) is our stable digital currency.\n"
        "• 1 FTC = 1 ZAR (always)\n"
        "• No price swings or volatility\n"
        "• Safe to borrow and lend\n\n"
        "*How it works:*\n"
        "1. Get loan in FTC\n"
        "2. Convert to ZAR with /offramp\n"
        "3. Buy FTC back with /buyftc to repay\n"
        "4. Repay loan in FTC\n\n"
        "*Common commands:*\n"
        "• /balance - Check your FTC balance\n"
        "• /offramp 1000 - Sell 1000 FTC for R1000\n"
        "• /buyftc 1000 - Buy 1000 FTC with R1000\n"
    )


def render_fees_category() -> str:
    return (
        "💸 *About Fees & Charges*\n\n"
        "Nkadime charges fair, transparent fees:\n\n"
        "*Interest Rates:*\n"
        "• 8-26% APR based on your credit score\n"
        "• Rate shown clearly before you accept the loan\n"
        "• Higher reputation = lower interest rate\n\n"
        "*Late Payment Fees:*\n"
        "• Grace period: 7 days (no fee)\n"
        "• After grace: R50-R100 depending on loan size\n"
        "• Fee added to your loan balance\n\n"
        "*Platform Service:*\n"
        "• Small percentage (1-4%) goes to Nkadime\n"
        "• Pays for platform operations\n"
        "• Shown in your repayment breakdown\n\n"
        "*No Hidden Fees:*\n"
        "• No application fees\n"
        "• No early repayment penalties\n"
        "• No monthly maintenance fees\n"
    )


# NOTE FROM (SANANA): Matching Tech Spec
# def render_loan_category() -> str:
#     return (
#         "💳 *Loan Application*\n\n"
#         "Apply directly in chat with /apply. We'll guide you through linking your bank data, "
#         "checking eligibility, and showing a transparent offer before you accept."
#     )
def render_loan_category() -> str:
    return (
        "💳 *Loan Application*\n\n"
        "Here's what I can help with:\n"
        " • How to apply\n"
        " • Why my application failed\n"
        " • Document requirements\n\n"
        "Select a topic:"
    )


def render_repay_category() -> str:
    return (
        "🧾 *Repayment*\n\n"
        "Repay in FTC with /repay. You can repay early without penalties. "
        "Use /offramp and /buyftc to move between ZAR and FTC as needed."
    )


def render_score_category() -> str:
    return (
        "📈 *Credit Score*\n\n"
        "Your on-platform score improves as you repay on time. Higher scores can unlock lower rates and larger limits. "
        "Use /score to see your current standing."
    )


def render_general_category() -> str:
    return (
        "❓ *General Questions*\n\n"
        f"{available_commands()}\n\n"
        "Need something else? Ask here, or contact support."
    )


# Q&A answers
def render_answer(cb: str) -> str:
    if cb == f"{CB_Q}ftc:get":
        return (
            "You get FTC by:\n"
            "• Receiving a loan in FTC via /apply\n"
            "• Buying FTC via /buyftc (convert ZAR → FTC)\n"
            "• Receiving FTC from another user via /send"
        )
    if cb == f"{CB_Q}ftc:safe":
        return (
            "Yes. FTC is designed to be stable (1 FTC = 1 ZAR) and is used only for borrowing and repayment on the platform. "
            "There's no speculative exposure or price volatility."
        )
    if cb == f"{CB_Q}fees:avoid":
        return (
            "Pay on time to avoid late fees. We provide a 7-day grace period. "
            "Turn on reminders, and consider early repayment—there's no penalty."
        )
    if cb == f"{CB_Q}fees:why":
        return (
            "Interest rates vary with risk: your credit score, repayment history, and affordability analysis determine the APR. "
            "Build reputation to unlock lower rates over time."
        )
    # NOTE FROM (SANANA): Adding these as responses to the 3 options bot gives when user selects [Loan Application]
    if cb == f"{CB_Q}loan:howtoapply":
        return (
            "📝 *To apply for a loan:*\n\n"
            "1. Type /apply\n"
            "2. Provide your ID and selfie\n"
            "3. Link your ABSA account\n"
            "4. Wait for credit assessment\n"
            "5. Accept loan offer if eligible\n\n"
            "Once accepted, funds will be disbursed within 24 hours."
        )
    if cb == f"{CB_Q}loan:whyfailed":
        return (
            "Your application may fail if:\n"
            "• The provided documents are invalid or blurry\n"
            "• Your credit score or affordability check fails\n"
            "• Your linked account cannot be verified\n\n"
            "You can retry after fixing any issues."
        )
    if cb == f"{CB_Q}loan:docs":
        return (
            "Required documents:\n"
            "• Valid South African ID\n"
            "• Clear selfie for verification\n"
            "• Linked ABSA account for disbursement\n"
        )
    return "I didn't catch that—please pick an option from the menu."


# ---------------------------
# HelpCommand
# ---------------------------


@register(
    name=CMD, aliases=["/help"], description="Help/Information", permission="public"
)
class HelpCommand(BaseCommand):
    name = CMD
    description = "Help/Information"
    permission = "public"

    def handle(self, message: TelegramMessage) -> None:
        self.task.delay(self.serialize(message))

    @shared_task(queue="telegram_bot")
    def task(message_data: dict) -> None:
        msg = TelegramMessage.from_payload(message_data)
        fsm = FSMStore()
        state = fsm.get(msg.chat_id)

        # Start menu if no state
        if not state:
            data = {}
            start_flow(fsm, msg.chat_id, CMD, data, S_MENU)
            # Initial header + menu
            reply(msg, intro_header(), kb_help_menu(), data=data)
            return

        # Guard: only handle our own flow
        if state.get("command") != CMD:
            return

        step = state.get("step") or S_MENU
        data = state.get("data", {}) or {}
        cb = getattr(msg, "callback_data", None)
        text = (msg.text or "").strip()

        # Always clear previous keyboard if present
        mark_prev_keyboard(data, msg)

        # Navigate back to menu
        if cb == CB_MENU:
            start_flow(fsm, msg.chat_id, CMD, data, S_MENU)
            reply(msg, intro_header(), kb_help_menu(), data=data)
            return

        # Main menu actions (callbacks)
        if cb and cb.startswith(CB_CAT):
            cat = cb.split(CB_CAT, 1)[1]
            if cat == CAT_FTC:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_FTC)
                reply(msg, render_ftc_category(), kb_ftc(), data=data)
                return
            if cat == CAT_FEES:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_FEES)
                reply(msg, render_fees_category(), kb_fees(), data=data)
                return
            if cat == CAT_LOAN:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_LOAN)
                # NOTE FROM (SANANA): We update this one to make use of kb_loan() for if user chooses [Loan Application]
                # reply(msg, render_loan_category(), kb_simple_back(), data=data)
                reply(msg, render_loan_category(), kb_loan(), data=data)
                return
            if cat == CAT_REPAY:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_REPAY)
                reply(msg, render_repay_category(), kb_simple_back(), data=data)
                return
            if cat == CAT_SCORE:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_SCORE)
                reply(msg, render_score_category(), kb_simple_back(), data=data)
                return
            if cat == CAT_GENERAL:
                start_flow(fsm, msg.chat_id, CMD, data, S_CAT_GENERAL)
                reply(msg, render_general_category(), kb_simple_back(), data=data)
                return

        # Q&A inside categories
        if cb and cb.startswith(CB_Q):
            # Re-render the category header + the specific answer, then keep its keyboard
            answer = render_answer(cb)
            if step == S_CAT_FTC:
                reply(
                    msg,
                    f"{render_ftc_category()}\n\n*Q&A*\n{answer}",
                    kb_ftc(),
                    data=data,
                )
                return
            if step == S_CAT_FEES:
                reply(
                    msg,
                    f"{render_fees_category()}\n\n*Q&A*\n{answer}",
                    kb_fees(),
                    data=data,
                )
                return
            # NOTE (SANANA): Adding this so just like ftc and fees, the answer AND loan sub-menu both show instead of the generic menu
            if step == S_CAT_LOAN:
                reply(
                    msg,
                    f"{render_loan_category()}\n\n*Q&A*\n{answer}",
                    kb_loan(),
                    data=data,
                )
                return
            # For other categories just show the answer with back
            reply(msg, answer, kb_simple_back(), data=data)
            return

        # if user pressed cancel/close
        if cb == "flow:cancel":
            clear_flow(fsm, msg.chat_id)
            reply(msg, "Help session closed. Use /help to start again.", data=data)
            return

        # If user typed anything instead of tapping
        if step == S_MENU:
            reply(msg, intro_header(), kb_help_menu(), data=data)
            return

        # In a subcategory, any text → show same subcategory content again
        if step == S_CAT_FTC:
            reply(msg, render_ftc_category(), kb_ftc(), data=data)
            return
        if step == S_CAT_FEES:
            reply(msg, render_fees_category(), kb_fees(), data=data)
            return
        # NOTE FROM (SANANA): should also use kb_loan()
        if step == S_CAT_LOAN:
            reply(msg, render_loan_category(), kb_loan(), data=data)
            return
        if step == S_CAT_REPAY:
            reply(msg, render_repay_category(), kb_simple_back(), data=data)
            return
        if step == S_CAT_SCORE:
            reply(msg, render_score_category(), kb_simple_back(), data=data)
            return
        if step == S_CAT_GENERAL:
            reply(msg, render_general_category(), kb_simple_back(), data=data)
            return

        # Fallback → reset
        clear_flow(fsm, msg.chat_id)
        reply(msg, "Session lost. Please /help again.")
