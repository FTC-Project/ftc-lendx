from __future__ import annotations

from typing import Dict, Optional, List, Tuple
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
from backend.apps.users.models import TelegramUser

# Command + steps
CMD = "help"

S_MENU = "menu"
S_COMMANDS = "commands"
S_GETTING_STARTED = "getting_started"
S_BORROWER_GUIDE = "borrower_guide"
S_LENDER_GUIDE = "lender_guide"
S_FTC_INFO = "ftc_info"
S_FAQS = "faqs"
S_LOAN_PROCESS = "loan_process"
S_REPAYMENT = "repayment"
S_POOL_DEPOSITS = "pool_deposits"
S_POOL_WITHDRAWALS = "pool_withdrawals"

# Callback prefixes
CB_MENU = "help:menu"
CB_SECTION = "help:section:"
CB_FAQ = "help:faq:"

# Section keys
SECTION_COMMANDS = "commands"
SECTION_GETTING_STARTED = "getting_started"
SECTION_BORROWER_GUIDE = "borrower_guide"
SECTION_LENDER_GUIDE = "lender_guide"
SECTION_FTC_INFO = "ftc_info"
SECTION_FAQS = "faqs"
SECTION_LOAN_PROCESS = "loan_process"
SECTION_REPAYMENT = "repayment"
SECTION_POOL_DEPOSITS = "pool_deposits"
SECTION_POOL_WITHDRAWALS = "pool_withdrawals"

# FAQ keys
FAQ_WHAT_IS_NKADIME = "what_is_nkadime"
FAQ_HOW_TO_START = "how_to_start"
FAQ_HOW_TO_REGISTER = "how_to_register"
FAQ_HOW_TO_BORROW = "how_to_borrow"
FAQ_HOW_TO_LEND = "how_to_lend"
FAQ_WHAT_IS_FTC = "what_is_ftc"
FAQ_HOW_TO_GET_FTC = "how_to_get_ftc"
FAQ_REPAYMENT_OPTIONS = "repayment_options"
FAQ_LATE_PAYMENTS = "late_payments"
FAQ_INTEREST_RATES = "interest_rates"
FAQ_POOL_SAFETY = "pool_safety"
FAQ_WITHDRAWAL_TIME = "withdrawal_time"
FAQ_CREDIT_SCORE = "credit_score"
FAQ_LINK_BANK = "link_bank"
FAQ_SUPPORT = "support"


# ---------------------------
# Keyboards
# ---------------------------


def _kb(inline_rows: List[List[Dict]]) -> dict:
    return {"inline_keyboard": inline_rows}


def get_user_role(msg: TelegramMessage) -> Tuple[Optional[TelegramUser], str]:
    """Returns (user, role_status) where role_status is: 'unregistered', 'user', 'borrower', 'lender'"""
    user = TelegramUser.objects.filter(telegram_id=msg.user_id).first()
    if not user or not user.is_active:
        return None, "unregistered"
    if not user.is_registered:
        return user, "user"
    return user, user.role or "user"


def kb_main_menu(role_status: str) -> dict:
    """Main menu based on user role"""
    if role_status == "unregistered":
        rows = [
            [
                {
                    "text": "🚀 Getting Started",
                    "callback_data": f"{CB_SECTION}{SECTION_GETTING_STARTED}",
                }
            ],
            [
                {
                    "text": "📚 All Commands",
                    "callback_data": f"{CB_SECTION}{SECTION_COMMANDS}",
                }
            ],
            [
                {
                    "text": "💰 About FTCoin",
                    "callback_data": f"{CB_SECTION}{SECTION_FTC_INFO}",
                }
            ],
            [{"text": "❓ FAQs", "callback_data": f"{CB_SECTION}{SECTION_FAQS}"}],
            [{"text": "❌ Close", "callback_data": "flow:cancel"}],
        ]
    elif role_status == "borrower":
        rows = [
            [
                {
                    "text": "📋 All Commands",
                    "callback_data": f"{CB_SECTION}{SECTION_COMMANDS}",
                }
            ],
            [
                {
                    "text": "💳 Borrower Guide",
                    "callback_data": f"{CB_SECTION}{SECTION_BORROWER_GUIDE}",
                }
            ],
            [
                {
                    "text": "🔄 Loan Process",
                    "callback_data": f"{CB_SECTION}{SECTION_LOAN_PROCESS}",
                }
            ],
            [
                {
                    "text": "💵 Repayment",
                    "callback_data": f"{CB_SECTION}{SECTION_REPAYMENT}",
                }
            ],
            [
                {
                    "text": "💰 About FTCoin",
                    "callback_data": f"{CB_SECTION}{SECTION_FTC_INFO}",
                }
            ],
            [{"text": "❓ FAQs", "callback_data": f"{CB_SECTION}{SECTION_FAQS}"}],
            [{"text": "❌ Close", "callback_data": "flow:cancel"}],
        ]
    elif role_status == "lender":
        rows = [
            [
                {
                    "text": "📋 All Commands",
                    "callback_data": f"{CB_SECTION}{SECTION_COMMANDS}",
                }
            ],
            [
                {
                    "text": "💼 Lender Guide",
                    "callback_data": f"{CB_SECTION}{SECTION_LENDER_GUIDE}",
                }
            ],
            [
                {
                    "text": "💰 Pool & Deposits",
                    "callback_data": f"{CB_SECTION}{SECTION_POOL_DEPOSITS}",
                }
            ],
            [
                {
                    "text": "💸 Withdrawals",
                    "callback_data": f"{CB_SECTION}{SECTION_POOL_WITHDRAWALS}",
                }
            ],
            [
                {
                    "text": "💰 About FTCoin",
                    "callback_data": f"{CB_SECTION}{SECTION_FTC_INFO}",
                }
            ],
            [{"text": "❓ FAQs", "callback_data": f"{CB_SECTION}{SECTION_FAQS}"}],
            [{"text": "❌ Close", "callback_data": "flow:cancel"}],
        ]
    else:  # user (registered but role unclear or general)
        rows = [
            [
                {
                    "text": "📋 All Commands",
                    "callback_data": f"{CB_SECTION}{SECTION_COMMANDS}",
                }
            ],
            [
                {
                    "text": "🚀 Getting Started",
                    "callback_data": f"{CB_SECTION}{SECTION_GETTING_STARTED}",
                }
            ],
            [
                {
                    "text": "💰 About FTCoin",
                    "callback_data": f"{CB_SECTION}{SECTION_FTC_INFO}",
                }
            ],
            [{"text": "❓ FAQs", "callback_data": f"{CB_SECTION}{SECTION_FAQS}"}],
            [{"text": "❌ Close", "callback_data": "flow:cancel"}],
        ]
    return _kb(rows)


def kb_back_to_menu() -> dict:
    return _kb([[{"text": "⬅️ Back to Menu", "callback_data": CB_MENU}]])


def kb_faq_menu(role_status: str) -> dict:
    """FAQ menu based on role"""
    rows = []
    if role_status == "unregistered":
        rows.extend(
            [
                [
                    {
                        "text": "What is Nkadime?",
                        "callback_data": f"{CB_FAQ}{FAQ_WHAT_IS_NKADIME}",
                    }
                ],
                [
                    {
                        "text": "How do I get started?",
                        "callback_data": f"{CB_FAQ}{FAQ_HOW_TO_START}",
                    }
                ],
                [
                    {
                        "text": "How do I register?",
                        "callback_data": f"{CB_FAQ}{FAQ_HOW_TO_REGISTER}",
                    }
                ],
            ]
        )
    elif role_status == "borrower":
        rows.extend(
            [
                [
                    {
                        "text": "How do I apply for a loan?",
                        "callback_data": f"{CB_FAQ}{FAQ_HOW_TO_BORROW}",
                    }
                ],
                [
                    {
                        "text": "How do I repay my loan?",
                        "callback_data": f"{CB_FAQ}{FAQ_REPAYMENT_OPTIONS}",
                    }
                ],
                [
                    {
                        "text": "What if I'm late on payments?",
                        "callback_data": f"{CB_FAQ}{FAQ_LATE_PAYMENTS}",
                    }
                ],
                [
                    {
                        "text": "How are interest rates determined?",
                        "callback_data": f"{CB_FAQ}{FAQ_INTEREST_RATES}",
                    }
                ],
                [
                    {
                        "text": "What is my credit score?",
                        "callback_data": f"{CB_FAQ}{FAQ_CREDIT_SCORE}",
                    }
                ],
            ]
        )
    elif role_status == "lender":
        rows.extend(
            [
                [
                    {
                        "text": "How do I deposit to the pool?",
                        "callback_data": f"{CB_FAQ}{FAQ_HOW_TO_LEND}",
                    }
                ],
                [
                    {
                        "text": "Is the pool safe?",
                        "callback_data": f"{CB_FAQ}{FAQ_POOL_SAFETY}",
                    }
                ],
                [
                    {
                        "text": "How long do withdrawals take?",
                        "callback_data": f"{CB_FAQ}{FAQ_WITHDRAWAL_TIME}",
                    }
                ],
            ]
        )

    # Common FAQs for all
    rows.extend(
        [
            [
                {
                    "text": "What is FTCoin (FTC)?",
                    "callback_data": f"{CB_FAQ}{FAQ_WHAT_IS_FTC}",
                }
            ],
            [
                {
                    "text": "How do I get FTC?",
                    "callback_data": f"{CB_FAQ}{FAQ_HOW_TO_GET_FTC}",
                }
            ],
            [
                {
                    "text": "How do I link my bank?",
                    "callback_data": f"{CB_FAQ}{FAQ_LINK_BANK}",
                }
            ],
            [{"text": "Need more help?", "callback_data": f"{CB_FAQ}{FAQ_SUPPORT}"}],
        ]
    )
    rows.append([{"text": "⬅️ Back to Menu", "callback_data": CB_MENU}])
    return _kb(rows)


# ---------------------------
# Content Renderers
# ---------------------------


def render_intro_header(role_status: str) -> str:
    if role_status == "unregistered":
        return (
            "🤝 <b>Nkadime Help Center</b>\n\n"
            "Welcome! Get help with using Nkadime to access affordable credit.\n\n"
            "What do you need help with?"
        )
    elif role_status == "borrower":
        return (
            "🤝 <b>Nkadime Help Center</b>\n\n"
            "Hello! Get help with borrowing, loans, and managing your account.\n\n"
            "What do you need help with?"
        )
    elif role_status == "lender":
        return (
            "🤝 <b>Nkadime Help Center</b>\n\n"
            "Hello! Get help with lending, deposits, and earning interest.\n\n"
            "What do you need help with?"
        )
    else:
        return (
            "🤝 <b>Nkadime Help Center</b>\n\n"
            "Get help with using Nkadime.\n\n"
            "What do you need help with?"
        )


def render_commands(user: Optional[TelegramUser], role_status: str) -> str:
    """Render all available commands based on user role"""
    text = "📋 <b>All Available Commands</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    # Public commands
    text += "🌐 <b>Public Commands (Everyone)</b>\n\n"
    text += "• /start - Welcome and accept Terms of Service\n"
    text += "• /help - Show this help menu\n\n"

    if role_status == "unregistered":
        text += "💡 <i>Register to unlock more commands. Use /start to begin!</i>\n"
        return text

    # User commands (registered)
    text += "👤 <b>Registered User Commands</b>\n\n"
    text += "• /register - Complete registration and KYC verification\n"
    text += "• /balance - Check your FTC, CTT, and XRP token balances\n"
    text += "• /linkbank - Link your bank account for loan applications\n"
    text += "• /score - View your credit score (CTT tokens) and tips\n"
    text += "• /buyftc - Buy FTCoin with ZAR\n"
    text += "• /offramp - Convert FTCoin to ZAR\n\n"

    if role_status == "borrower":
        text += "💳 <b>Borrower Commands</b>\n\n"
        text += "• /apply - Apply for a loan\n"
        text += "• /status - Check your most recent loan status\n"
        text += "• /repay - Repay your loan\n"
        text += "• /history - View your loan history\n\n"

    if role_status == "lender":
        text += "💰 <b>Lender Commands</b>\n\n"
        text += "• /deposit - Deposit FTCT to the lending pool\n"
        text += "• /withdraw - Withdraw FTCT from the lending pool\n"
        text += "• /balance - View pool balance and deposit/withdrawal history\n\n"

    text += "💡 <i>Tip: Commands are case-insensitive. Use any command to see interactive guidance.</i>"
    return text


def render_getting_started() -> str:
    return (
        "🚀 <b>Getting Started with Nkadime</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Step 1: Accept Terms of Service</b>\n"
        "Use /start to begin. You'll need to accept our Terms of Service to create your account.\n\n"
        "<b>Step 2: Complete Registration</b>\n"
        "Use /register to complete your profile:\n"
        "• Confirm your personal information\n"
        "• Verify your phone number\n"
        "• Upload your SA ID photo\n"
        "• Select your role (Borrower or Lender)\n\n"
        "<b>Step 3: Choose Your Path</b>\n\n"
        "<b>👉 For Borrowers:</b>\n"
        "1. Link your bank: /linkbank\n"
        "2. Check your credit score: /score\n"
        "3. Apply for a loan: /apply\n\n"
        "<b>👉 For Lenders:</b>\n"
        "1. Buy FTCoin: /buyftc\n"
        "2. Deposit to pool: /deposit\n"
        "3. Earn interest on your deposits\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 <i>Need help? Use /help anytime or browse our FAQs!</i>"
    )


def render_borrower_guide() -> str:
    return (
        "💳 <b>Borrower's Complete Guide</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📝 Your Journey as a Borrower</b>\n\n"
        "<b>1. Setup (One-Time)</b>\n"
        "• Complete registration: /register\n"
        "• Link your bank account: /linkbank\n"
        "• Build your credit score: /score\n\n"
        "<b>2. Apply for a Loan</b>\n"
        "• Start application: /apply\n"
        "• Select loan amount and term\n"
        "• Review your personalized offer (interest rate, fees)\n"
        "• Accept if terms are favorable\n\n"
        "<b>3. Receive Your Loan</b>\n"
        "• Loan is disbursed in FTCoin (FTC)\n"
        "• Check balance: /balance\n"
        "• Convert to ZAR: /offramp\n\n"
        "<b>4. Manage Your Loan</b>\n"
        "• Check status: /status\n"
        "• View history: /history\n"
        "• Monitor repayment schedule\n\n"
        "<b>5. Repay Your Loan</b>\n"
        "• Buy FTC if needed: /buyftc\n"
        "• Repay: /repay\n"
        "• Early repayment has no penalties!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>💡 Tips for Success</b>\n"
        "• Repay on time to improve your credit score\n"
        "• Higher scores unlock lower interest rates\n"
        "• Always check your loan status before repayments\n"
        "• Use /help if you're stuck!"
    )


def render_lender_guide() -> str:
    return (
        "💼 <b>Lender's Complete Guide</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>💰 Your Journey as a Lender</b>\n\n"
        "<b>1. Setup (One-Time)</b>\n"
        "• Complete registration: /register\n"
        "• Select 'Lender' as your role\n"
        "• Your wallet is automatically created\n\n"
        "<b>2. Fund Your Account</b>\n"
        "• Buy FTCoin: /buyftc\n"
        "• Convert ZAR to FTC at 1:1 rate\n"
        "• Check balance: /balance\n\n"
        "<b>3. Deposit to Pool</b>\n"
        "• View pool details: /deposit\n"
        "• Review current APY and pool statistics\n"
        "• Follow the secure deposit process\n"
        "• Your deposit earns interest immediately\n\n"
        "<b>4. Monitor Earnings</b>\n"
        "• Check balance: /balance\n"
        "• View deposit history\n"
        "• Track your earnings growth\n\n"
        "<b>5. Withdraw Funds</b>\n"
        "• Withdraw anytime: /withdraw\n"
        "• No lock-in periods\n"
        "• Convert to ZAR: /offramp\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>💡 Tips for Success</b>\n"
        "• Larger deposits may earn better rates\n"
        "• Keep funds in pool to maximize earnings\n"
        "• Monitor pool performance regularly\n"
        "• Use /help for any questions!"
    )


def render_ftc_info() -> str:
    return (
        "💰 <b>About FTCoin (FTC)</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>What is FTCoin?</b>\n"
        "FTCoin (FTC) is Nkadime's stable digital currency designed for borrowing and lending.\n\n"
        "<b>🔒 Stability</b>\n"
        "• 1 FTC = 1 ZAR (always)\n"
        "• No price volatility\n"
        "• Safe for both borrowers and lenders\n\n"
        "<b>💵 How It Works</b>\n"
        "1. <b>Borrowers:</b> Receive loans in FTC, convert to ZAR, repay in FTC\n"
        "2. <b>Lenders:</b> Deposit FTC to earn interest, withdraw anytime\n\n"
        "<b>🔄 Conversion Commands</b>\n"
        "• /buyftc [amount] - Buy FTC with ZAR\n"
        "• /offramp [amount] - Sell FTC for ZAR\n\n"
        "<b>📊 Checking Your Balance</b>\n"
        "• /balance - View FTC, CTT, and XRP balances\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>⚠️ Important Notes</b>\n"
        "• FTC is used exclusively on the Nkadime platform\n"
        "• Conversion rates are fixed at 1:1 with ZAR\n"
        "• Always check your balance before transactions\n"
        "• Keep some XRP for gas fees (blockchain transactions)"
    )


def render_loan_process() -> str:
    return (
        "🔄 <b>Loan Application Process</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Step-by-Step Guide</b>\n\n"
        "<b>1. Prerequisites</b>\n"
        "✓ Complete registration: /register\n"
        "✓ Link your bank account: /linkbank\n"
        "✓ Check your credit score: /score\n\n"
        "<b>2. Start Application</b>\n"
        "• Use command: /apply\n"
        "• Review your available credit limit\n\n"
        "<b>3. Select Loan Details</b>\n"
        "• Choose loan amount (within your limit)\n"
        "• Select repayment term (days)\n"
        "• Review estimated interest rate\n\n"
        "<b>4. Review Offer</b>\n"
        "• See detailed breakdown:\n"
        "  - Principal amount\n"
        "  - Interest rate (APR)\n"
        "  - Total repayable\n"
        "  - Payment schedule\n\n"
        "<b>5. Accept or Decline</b>\n"
        "• Accept if terms are acceptable\n"
        "• Decline to try again later\n\n"
        "<b>6. Receive Funds</b>\n"
        "• Loan disbursed in FTCoin\n"
        "• Check: /balance\n"
        "• Convert to ZAR: /offramp\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>💡 Tips</b>\n"
        "• Higher credit scores = lower interest rates\n"
        "• Shorter terms may have lower total interest\n"
        "• Always review the full repayment schedule\n"
        "• Check loan status: /status"
    )


def render_repayment() -> str:
    return (
        "💵 <b>Repayment Guide</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>How to Repay</b>\n\n"
        "<b>1. Check Your Loan Status</b>\n"
        "• Use /status to see:\n"
        "  - Current balance\n"
        "  - Amount repaid\n"
        "  - Next due date\n"
        "  - Final due date\n\n"
        "<b>2. Get FTCoin</b>\n"
        "• If you need FTC: /buyftc [amount]\n"
        "• Check balance: /balance\n\n"
        "<b>3. Make Repayment</b>\n"
        "• Use: /repay\n"
        "• Select repayment amount\n"
        "• Confirm transaction\n\n"
        "<b>4. Track Progress</b>\n"
        "• Check status: /status\n"
        "• View history: /history\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📅 Repayment Options</b>\n\n"
        "• <b>Full Repayment:</b> Pay off entire loan\n"
        "• <b>Partial Repayment:</b> Pay any amount towards balance\n"
        "• <b>Early Repayment:</b> No penalties! Pay anytime\n\n"
        "<b>⚠️ Important</b>\n"
        "• Grace period: 7 days after due date\n"
        "• Late fees apply after grace period\n"
        "• On-time payments improve credit score\n"
        "• Always keep some XRP for gas fees\n\n"
        "<b>💡 Pro Tip</b>\n"
        "Set reminders before due dates. Repaying early can improve your credit score faster!"
    )


def render_pool_deposits() -> str:
    return (
        "💰 <b>Pool Deposits Guide</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>How to Deposit</b>\n\n"
        "<b>1. Prepare Your Funds</b>\n"
        "• Buy FTCoin: /buyftc [amount]\n"
        "• Check balance: /balance\n"
        "• Ensure you have XRP for gas fees\n\n"
        "<b>2. View Pool Details</b>\n"
        "• Use: /deposit\n"
        "• Review:\n"
        "  - Current APY (Annual Percentage Yield)\n"
        "  - Pool size\n"
        "  - Your current deposits\n"
        "  - Total earnings\n\n"
        "<b>3. Deposit Process</b>\n"
        "• Click 'Deposit' button\n"
        "• Open secure deposit page\n"
        "• Follow on-chain transaction steps:\n"
        "  1. Approve FTCT spending\n"
        "  2. Deposit to pool contract\n"
        "  3. Wait for blockchain confirmation\n\n"
        "<b>4. Confirmation</b>\n"
        "• Transaction appears in history\n"
        "• Balance updates automatically\n"
        "• Start earning interest immediately\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>💡 Benefits</b>\n"
        "• Earn competitive interest rates\n"
        "• No lock-in periods\n"
        "• Transparent, on-chain transactions\n"
        "• Track all deposits: /balance\n\n"
        "<b>⚠️ Notes</b>\n"
        "• Keep some XRP for gas fees\n"
        "• Deposits are on-chain (blockchain)\n"
        "• Interest accrues continuously\n"
        "• Monitor pool performance regularly"
    )


def render_pool_withdrawals() -> str:
    return (
        "💸 <b>Withdrawals Guide</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>How to Withdraw</b>\n\n"
        "<b>1. Check Your Balance</b>\n"
        "• Use: /balance\n"
        "• View available FTCT in pool\n"
        "• Check deposit history\n\n"
        "<b>2. Initiate Withdrawal</b>\n"
        "• Use: /withdraw\n"
        "• Select withdrawal amount\n"
        "• Confirm transaction\n\n"
        "<b>3. On-Chain Process</b>\n"
        "• Transaction submitted to blockchain\n"
        "• Wait for confirmation (usually quick)\n"
        "• Funds appear in your wallet\n\n"
        "<b>4. Convert to ZAR (Optional)</b>\n"
        "• Use: /offramp [amount]\n"
        "• Convert FTCT to ZAR\n"
        "• 1 FTC = R1.00\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>✅ Withdrawal Features</b>\n"
        "• No lock-in periods\n"
        "• Withdraw anytime\n"
        "• No withdrawal fees\n"
        "• Fast processing\n\n"
        "<b>⚠️ Important Notes</b>\n"
        "• Keep XRP for gas fees\n"
        "• Withdrawals are on-chain\n"
        "• Check balance before withdrawing\n"
        "• Large withdrawals may require multiple transactions"
    )


def render_faq_answer(faq_key: str) -> str:
    """Render FAQ answers"""
    faqs = {
        FAQ_WHAT_IS_NKADIME: (
            "🏦 <b>What is Nkadime?</b>\n\n"
            "Nkadime is a platform that helps you access affordable credit using your banking data. "
            "We use blockchain technology to make borrowing and lending transparent and efficient.\n\n"
            "<b>Key Features:</b>\n"
            "• Affordable loans based on your creditworthiness\n"
            "• Earn interest as a lender\n"
            "• Blockchain-powered transparency\n"
            "• No hidden fees\n\n"
            "<b>How It Works:</b>\n"
            "1. <b>Borrowers:</b> Link bank → Apply → Receive loan in FTCoin → Repay\n"
            "2. <b>Lenders:</b> Deposit FTCoin → Earn interest → Withdraw anytime\n\n"
            "Start with /start to create your account!"
        ),
        FAQ_HOW_TO_START: (
            "🚀 <b>How Do I Get Started?</b>\n\n"
            "<b>Step 1:</b> Use /start\n"
            "• Accept Terms of Service\n"
            "• Create your account\n\n"
            "<b>Step 2:</b> Complete Registration\n"
            "• Use /register\n"
            "• Provide your information\n"
            "• Upload ID photo\n"
            "• Select role (Borrower or Lender)\n\n"
            "<b>Step 3:</b> Choose Your Path\n"
            "• <b>Borrowers:</b> /linkbank → /apply\n"
            "• <b>Lenders:</b> /buyftc → /deposit\n\n"
            "Need help? Use /help anytime!"
        ),
        FAQ_HOW_TO_REGISTER: (
            "📝 <b>How Do I Register?</b>\n\n"
            "Use /register and follow these steps:\n\n"
            "<b>1. Personal Information</b>\n"
            "• Confirm first name\n"
            "• Confirm last name\n"
            "• Provide phone number (+27XXXXXXXXX)\n"
            "• Provide SA ID number (13 digits)\n\n"
            "<b>2. Select Role</b>\n"
            "• Choose Borrower or Lender\n"
            "• You can focus on one role\n\n"
            "<b>3. Upload ID</b>\n"
            "• Upload clear photo of SA ID (front)\n"
            "• Ensure text is readable\n\n"
            "<b>4. Review & Confirm</b>\n"
            "• Check all information\n"
            "• Confirm registration\n\n"
            "Once complete, you'll be verified and can start using all features!"
        ),
        FAQ_HOW_TO_BORROW: (
            "💳 <b>How Do I Apply for a Loan?</b>\n\n"
            "<b>Prerequisites:</b>\n"
            "✓ Registered and verified\n"
            "✓ Bank account linked: /linkbank\n"
            "✓ Credit score checked: /score\n\n"
            "<b>Application Steps:</b>\n\n"
            "<b>1. Start Application</b>\n"
            "• Use: /apply\n"
            "• Review your credit limit\n\n"
            "<b>2. Choose Loan Details</b>\n"
            "• Select amount (within limit)\n"
            "• Choose repayment term\n\n"
            "<b>3. Review Offer</b>\n"
            "• See interest rate (APR)\n"
            "• Review total repayable\n"
            "• Check payment schedule\n\n"
            "<b>4. Accept & Receive</b>\n"
            "• Accept if terms suit you\n"
            "• Loan disbursed in FTCoin\n"
            "• Convert to ZAR: /offramp\n\n"
            "<b>💡 Tip:</b> Higher credit scores unlock lower interest rates!"
        ),
        FAQ_HOW_TO_LEND: (
            "💰 <b>How Do I Deposit to the Pool?</b>\n\n"
            "<b>Step 1: Get FTCoin</b>\n"
            "• Buy FTC: /buyftc [amount]\n"
            "• 1 FTC = R1.00\n\n"
            "<b>Step 2: View Pool</b>\n"
            "• Use: /deposit\n"
            "• See current APY\n"
            "• Review pool statistics\n\n"
            "<b>Step 3: Deposit</b>\n"
            "• Click 'Deposit' button\n"
            "• Follow secure on-chain process\n"
            "• Wait for confirmation\n\n"
            "<b>Step 4: Earn Interest</b>\n"
            "• Start earning immediately\n"
            "• Check balance: /balance\n"
            "• Monitor your earnings\n\n"
            "<b>✅ Benefits:</b>\n"
            "• Competitive interest rates\n"
            "• No lock-in periods\n"
            "• Withdraw anytime: /withdraw"
        ),
        FAQ_WHAT_IS_FTC: (
            "💰 <b>What is FTCoin (FTC)?</b>\n\n"
            "FTCoin is Nkadime's stable digital currency.\n\n"
            "<b>Key Facts:</b>\n"
            "• 1 FTC = 1 ZAR (always stable)\n"
            "• No price volatility\n"
            "• Used for all loans and deposits\n"
            "• Blockchain-powered\n\n"
            "<b>How It's Used:</b>\n"
            "• <b>Borrowers:</b> Receive loans in FTC, repay in FTC\n"
            "• <b>Lenders:</b> Deposit FTC to earn interest\n\n"
            "<b>Commands:</b>\n"
            "• /buyftc - Buy FTC with ZAR\n"
            "• /offramp - Sell FTC for ZAR\n"
            "• /balance - Check your FTC balance\n\n"
            "FTC makes borrowing and lending simple and safe!"
        ),
        FAQ_HOW_TO_GET_FTC: (
            "💵 <b>How Do I Get FTCoin?</b>\n\n"
            "<b>Method 1: Buy FTC</b>\n"
            "• Use: /buyftc [amount]\n"
            "• Convert ZAR to FTC\n"
            "• Rate: 1 FTC = R1.00\n\n"
            "<b>Method 2: Receive Loan</b>\n"
            "• Apply for loan: /apply\n"
            "• Loan disbursed in FTCoin\n\n"
            "<b>Method 3: Receive Deposit (Lenders)</b>\n"
            "• Withdraw from pool: /withdraw\n"
            "• Receive FTCT in your wallet\n\n"
            "<b>Checking Your Balance:</b>\n"
            "• Use: /balance\n"
            "• See FTC, CTT, and XRP balances\n\n"
            "<b>💡 Note:</b> Always keep some XRP for gas fees (blockchain transactions)!"
        ),
        FAQ_REPAYMENT_OPTIONS: (
            "💵 <b>Repayment Options</b>\n\n"
            "<b>How to Repay:</b>\n"
            "• Use: /repay\n"
            "• Select repayment amount\n"
            "• Confirm transaction\n\n"
            "<b>Repayment Types:</b>\n\n"
            "<b>1. Full Repayment</b>\n"
            "• Pay entire remaining balance\n"
            "• Close your loan\n\n"
            "<b>2. Partial Repayment</b>\n"
            "• Pay any amount towards balance\n"
            "• Reduce your outstanding amount\n\n"
            "<b>3. Early Repayment</b>\n"
            "• No penalties!\n"
            "• Pay anytime before due date\n"
            "• Can improve credit score\n\n"
            "<b>Getting FTC for Repayment:</b>\n"
            "• Buy FTC: /buyftc [amount]\n"
            "• Check balance: /balance\n\n"
            "<b>📅 Important:</b> Check /status for due dates and balances!"
        ),
        FAQ_LATE_PAYMENTS: (
            "⚠️ <b>What If I'm Late on Payments?</b>\n\n"
            "<b>Grace Period:</b>\n"
            "• 7 days after due date\n"
            "• No fees during grace period\n"
            "• Still recommended to pay as soon as possible\n\n"
            "<b>After Grace Period:</b>\n"
            "• Late fees apply (R50-R100 depending on loan size)\n"
            "• Fee added to loan balance\n"
            "• Credit score may be affected\n\n"
            "<b>What to Do:</b>\n"
            "1. Repay as soon as possible: /repay\n"
            "2. Check status: /status\n"
            "3. Contact support if facing difficulties\n\n"
            "<b>💡 Tips:</b>\n"
            "• Set reminders before due dates\n"
            "• Early repayment has no penalties\n"
            "• On-time payments improve credit score\n"
            "• Check your loan schedule regularly"
        ),
        FAQ_INTEREST_RATES: (
            "📊 <b>How Are Interest Rates Determined?</b>\n\n"
            "<b>Rate Range:</b> 8-26% APR\n\n"
            "<b>Factors Affecting Your Rate:</b>\n\n"
            "<b>1. Credit Score (CTT)</b>\n"
            "• Higher score = Lower rate\n"
            "• Check score: /score\n\n"
            "<b>2. Repayment History</b>\n"
            "• On-time payments improve rates\n"
            "• Late payments increase rates\n\n"
            "<b>3. Affordability Analysis</b>\n"
            "• Based on linked bank data\n"
            "• Income vs expenses\n\n"
            "<b>4. Loan Amount & Term</b>\n"
            "• Larger loans may have different rates\n"
            "• Term length affects APR\n\n"
            "<b>💡 Improving Your Rate:</b>\n"
            "• Repay loans on time\n"
            "• Build credit history\n"
            "• Maintain good financial habits\n\n"
            "<b>📋 Note:</b> Your exact rate is shown before you accept any loan offer!"
        ),
        FAQ_POOL_SAFETY: (
            "🔒 <b>Is the Pool Safe?</b>\n\n"
            "<b>Security Measures:</b>\n\n"
            "<b>1. Blockchain Technology</b>\n"
            "• All transactions are on-chain\n"
            "• Transparent and auditable\n"
            "• Smart contract security\n\n"
            "<b>2. Smart Contracts</b>\n"
            "• Automated, no manual intervention\n"
            "• Code-reviewed processes\n"
            "• Immutable transaction history\n\n"
            "<b>3. Your Control</b>\n"
            "• You control your wallet\n"
            "• Private keys are encrypted\n"
            "• Withdraw anytime\n\n"
            "<b>4. Pool Management</b>\n"
            "• Diversified lending\n"
            "• Risk management protocols\n"
            "• Regular monitoring\n\n"
            "<b>⚠️ Important:</b>\n"
            "• Always keep your wallet secure\n"
            "• Never share your private keys\n"
            "• Verify transactions: /balance\n"
            "• Start with smaller deposits if unsure"
        ),
        FAQ_WITHDRAWAL_TIME: (
            "⏱️ <b>How Long Do Withdrawals Take?</b>\n\n"
            "<b>Withdrawal Process:</b>\n\n"
            "<b>1. Initiate Withdrawal</b>\n"
            "• Use: /withdraw\n"
            "• Select amount\n"
            "• Confirm transaction\n\n"
            "<b>2. Blockchain Confirmation</b>\n"
            "• Usually completes in minutes\n"
            "• On-chain transaction required\n"
            "• Status shown in real-time\n\n"
            "<b>3. Funds Available</b>\n"
            "• Appear in your wallet\n"
            "• Check: /balance\n\n"
            "<b>⏱️ Typical Timeline:</b>\n"
            "• Small withdrawals: 2-5 minutes\n"
            "• Larger withdrawals: 5-10 minutes\n"
            "• Network congestion may cause delays\n\n"
            "<b>💡 Tips:</b>\n"
            "• Ensure XRP balance for gas fees\n"
            "• Check blockchain status if delayed\n"
            "• Large amounts may require multiple transactions"
        ),
        FAQ_CREDIT_SCORE: (
            "📈 <b>What Is My Credit Score?</b>\n\n"
            "<b>Credit Score (CTT)</b>\n"
            "Your Credit Trust Tokens (CTT) represent your creditworthiness on Nkadime.\n\n"
            "<b>How to Check:</b>\n"
            "• Use: /score\n"
            "• View current CTT balance\n"
            "• See tips for improvement\n\n"
            "<b>How Scores Work:</b>\n"
            "• Start with base score\n"
            "• Increase with on-time repayments\n"
            "• Decrease with late payments\n"
            "• Higher scores = Lower interest rates\n\n"
            "<b>Improving Your Score:</b>\n"
            "✅ Repay loans on time\n"
            "✅ Complete full loan terms\n"
            "✅ Maintain good repayment history\n"
            "✅ Link and maintain bank account\n\n"
            "<b>💡 Impact:</b>\n"
            "• Scores range from low to high\n"
            "• Higher scores unlock:\n"
            "  - Lower interest rates (8-26% APR)\n"
            "  - Higher loan limits\n"
            "  - Better loan terms\n\n"
            "Check regularly: /score"
        ),
        FAQ_LINK_BANK: (
            "🏦 <b>How Do I Link My Bank Account?</b>\n\n"
            "<b>Why Link Bank?</b>\n"
            "• Required for loan applications\n"
            "• Enables affordability analysis\n"
            "• Helps determine creditworthiness\n\n"
            "<b>How to Link:</b>\n\n"
            "<b>1. Start Process</b>\n"
            "• Use: /linkbank\n"
            "• Follow guided setup\n\n"
            "<b>2. Bank Selection</b>\n"
            "• Select your bank\n"
            "• Choose account type\n\n"
            "<b>3. Authorization</b>\n"
            "• Complete OAuth process\n"
            "• Grant read-only access (secure)\n"
            "• We only read transaction data\n\n"
            "<b>4. Verification</b>\n"
            "• Bank data synced\n"
            "• Account verified\n"
            "• Ready for loan applications\n\n"
            "<b>🔒 Security:</b>\n"
            "• Read-only access (no withdrawals)\n"
            "• Encrypted data storage\n"
            "• Used only for affordability checks\n\n"
            "<b>💡 Note:</b> Linking bank is required before applying for loans!"
        ),
        FAQ_SUPPORT: (
            "💬 <b>Need More Help?</b>\n\n"
            "<b>Self-Service Options:</b>\n"
            "• Browse FAQs: /help\n"
            "• Check command descriptions\n"
            "• Review process guides\n\n"
            "<b>Common Commands for Help:</b>\n"
            "• /help - This help center\n"
            "• /status - Check loan status\n"
            "• /balance - View balances\n"
            "• /score - Credit score info\n\n"
            "<b>📚 Help Sections:</b>\n"
            "• Getting Started guides\n"
            "• Borrower/Lender guides\n"
            "• Command documentation\n"
            "• FAQ database\n\n"
            "<b>⚠️ For Technical Issues:</b>\n"
            "• Check your connection\n"
            "• Verify command spelling\n"
            "• Ensure you're registered: /register\n"
            "• Check role permissions\n\n"
            "<b>💡 Tip:</b> Most questions are answered in the /help menu. "
            "Browse by category to find what you need!"
        ),
    }
    return faqs.get(
        faq_key, "I couldn't find that FAQ. Please try again from the menu."
    )


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

        # Get user role for personalized menus
        user, role_status = get_user_role(msg)

        # Start menu if no state
        if not state:
            data = {"role_status": role_status}
            start_flow(fsm, msg.chat_id, CMD, data, S_MENU)
            # Initial header + menu
            reply(
                msg,
                render_intro_header(role_status),
                kb_main_menu(role_status),
                data=data,
                parse_mode="HTML",
            )
            return

        # Guard: only handle our own flow
        if state.get("command") != CMD:
            return

        step = state.get("step") or S_MENU
        data = state.get("data", {}) or {}
        cb = getattr(msg, "callback_data", None)
        text = (msg.text or "").strip()

        # Update role status in case it changed
        user, role_status = get_user_role(msg)
        data["role_status"] = role_status

        # Always clear previous keyboard if present
        mark_prev_keyboard(data, msg)

        # Navigate back to menu
        if cb == CB_MENU:
            start_flow(fsm, msg.chat_id, CMD, data, S_MENU)
            reply(
                msg,
                render_intro_header(role_status),
                kb_main_menu(role_status),
                data=data,
                parse_mode="HTML",
            )
            return

        # Handle section callbacks
        if cb and cb.startswith(CB_SECTION):
            section = cb.split(CB_SECTION, 1)[1]
            if section == SECTION_COMMANDS:
                start_flow(fsm, msg.chat_id, CMD, data, S_COMMANDS)
                reply(
                    msg,
                    render_commands(user, role_status),
                    kb_back_to_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                return
            elif section == SECTION_GETTING_STARTED:
                start_flow(fsm, msg.chat_id, CMD, data, S_GETTING_STARTED)
                reply(
                    msg,
                    render_getting_started(),
                    kb_back_to_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                return
            elif section == SECTION_BORROWER_GUIDE:
                start_flow(fsm, msg.chat_id, CMD, data, S_BORROWER_GUIDE)
                reply(
                    msg,
                    render_borrower_guide(),
                    kb_back_to_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                return
            elif section == SECTION_LENDER_GUIDE:
                start_flow(fsm, msg.chat_id, CMD, data, S_LENDER_GUIDE)
                reply(
                    msg,
                    render_lender_guide(),
                    kb_back_to_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                return
            elif section == SECTION_FTC_INFO:
                start_flow(fsm, msg.chat_id, CMD, data, S_FTC_INFO)
                reply(
                    msg,
                    render_ftc_info(),
                    kb_back_to_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                return
            elif section == SECTION_FAQS:
                start_flow(fsm, msg.chat_id, CMD, data, S_FAQS)
                reply(
                    msg,
                    "❓ <b>Frequently Asked Questions</b>\n\n"
                    "Select a question to see the answer:",
                    kb_faq_menu(role_status),
                    data=data,
                    parse_mode="HTML",
                )
                return
            elif section == SECTION_LOAN_PROCESS:
                start_flow(fsm, msg.chat_id, CMD, data, S_LOAN_PROCESS)
                reply(
                    msg,
                    render_loan_process(),
                    kb_back_to_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                return
            elif section == SECTION_REPAYMENT:
                start_flow(fsm, msg.chat_id, CMD, data, S_REPAYMENT)
                reply(
                    msg,
                    render_repayment(),
                    kb_back_to_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                return
            elif section == SECTION_POOL_DEPOSITS:
                start_flow(fsm, msg.chat_id, CMD, data, S_POOL_DEPOSITS)
                reply(
                    msg,
                    render_pool_deposits(),
                    kb_back_to_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                return
            elif section == SECTION_POOL_WITHDRAWALS:
                start_flow(fsm, msg.chat_id, CMD, data, S_POOL_WITHDRAWALS)
                reply(
                    msg,
                    render_pool_withdrawals(),
                    kb_back_to_menu(),
                    data=data,
                    parse_mode="HTML",
                )
                return

        # Handle FAQ callbacks
        if cb and cb.startswith(CB_FAQ):
            faq_key = cb.split(CB_FAQ, 1)[1]
            answer = render_faq_answer(faq_key)
            reply(
                msg,
                answer,
                kb_faq_menu(role_status),
                data=data,
                parse_mode="HTML",
            )
            return

        # if user pressed cancel/close
        if cb == "flow:cancel":
            clear_flow(fsm, msg.chat_id)
            reply(
                msg,
                "✅ <b>Help Session Closed</b>\n\n"
                "Use /help anytime to get help again!",
                data=data,
                parse_mode="HTML",
            )
            return

        # If user typed anything, show menu again
        if step == S_MENU:
            reply(
                msg,
                render_intro_header(role_status),
                kb_main_menu(role_status),
                data=data,
                parse_mode="HTML",
            )
            return

        # In a subcategory, show it again
        if step == S_COMMANDS:
            reply(
                msg,
                render_commands(user, role_status),
                kb_back_to_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        if step == S_GETTING_STARTED:
            reply(
                msg,
                render_getting_started(),
                kb_back_to_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        if step == S_BORROWER_GUIDE:
            reply(
                msg,
                render_borrower_guide(),
                kb_back_to_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        if step == S_LENDER_GUIDE:
            reply(
                msg,
                render_lender_guide(),
                kb_back_to_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        if step == S_FTC_INFO:
            reply(
                msg,
                render_ftc_info(),
                kb_back_to_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        if step == S_FAQS:
            reply(
                msg,
                "❓ <b>Frequently Asked Questions</b>\n\n"
                "Select a question to see the answer:",
                kb_faq_menu(role_status),
                data=data,
                parse_mode="HTML",
            )
            return
        if step == S_LOAN_PROCESS:
            reply(
                msg,
                render_loan_process(),
                kb_back_to_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        if step == S_REPAYMENT:
            reply(
                msg,
                render_repayment(),
                kb_back_to_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        if step == S_POOL_DEPOSITS:
            reply(
                msg,
                render_pool_deposits(),
                kb_back_to_menu(),
                data=data,
                parse_mode="HTML",
            )
            return
        if step == S_POOL_WITHDRAWALS:
            reply(
                msg,
                render_pool_withdrawals(),
                kb_back_to_menu(),
                data=data,
                parse_mode="HTML",
            )
            return

        # Fallback → reset
        clear_flow(fsm, msg.chat_id)
        reply(
            msg,
            "❌ <b>Session Lost</b>\n\n" "Please use /help again.",
            parse_mode="HTML",
        )
