from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from celery.result import AsyncResult
from backend.celery import app
from web3 import Web3
from django.conf import settings
from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.tokens.services.ftc_token import FTCTokenService
from backend.apps.loans.models import Loan
from backend.apps.sys_frontend.tasks import process_deposit_ftct
from backend.apps.pool.models import PoolDeposit, PoolWithdrawal
from backend.apps.users.models import Wallet
from backend.apps.users.services.deposit_code import DepositCodeService
from backend.apps.sys_frontend.deposit_status_store import DepositStatusStore


# Simple Ethereum wallet validation
def is_valid_wallet(wallet):
    return True


@csrf_exempt  # for testing only; remove in production
def deposit_ftct_view(request):
    try:
        if request.method == "GET":
            # Get one-time code from query params
            code = (request.GET.get("code") or "").strip()
            wallet_q = ""
            key_q = ""
            key_masked = ""
            
            # Retrieve wallet data from Redis using code
            if code:
                code_service = DepositCodeService()
                wallet_data = code_service.get_without_delete(code)
                if wallet_data:
                    wallet_q = wallet_data.get("wallet", "")
                    private_key_full = wallet_data.get("private_key", "")
                    # Mask private key: show first 6 chars, rest as dots
                    if private_key_full:
                        if len(private_key_full) > 6:
                            key_masked = private_key_full[:6] + "•" * (len(private_key_full) - 6)
                        else:
                            key_masked = private_key_full
                        # Store full key in a hidden field (will be sent in POST)
                        key_q = private_key_full

            # Fetch pool stats
            loan_service = LoanSystemService()
            total_pool = float(loan_service.get_total_pool())
            total_shares = float(loan_service.get_total_shares())
            user_shares = 0.0
            user_value = 0.0
            ftc_balance = None
            xrp_balance = None
            ftc_service = FTCTokenService()
            if wallet_q:
                try:
                    user_shares = float(loan_service.get_shares_of(wallet_q))
                    user_value = (
                        float(loan_service.get_share_value(user_shares))
                        if user_shares > 0
                        else 0.0
                    )
                    # Fetch balances for info panel
                    ftc_balance = float(ftc_service.get_balance(wallet_q))
                    xrp_balance = float(
                        ftc_service.web3.from_wei(
                            ftc_service.web3.eth.get_balance(wallet_q), "ether"
                        )
                    )
                    # Calculate PnL = current value - net contributed (sum deposits - sum withdrawals)
                    pnl = 0.0
                    pnl_color = "gray"
                    try:
                        w = Wallet.objects.filter(address=wallet_q).first()
                        if w:
                            deposits_sum = sum(
                                float(d.amount)
                                for d in PoolDeposit.objects.filter(user=w.user)
                            )
                            withdrawals_sum = sum(
                                float(wd.principal_out + wd.interest_out)
                                for wd in PoolWithdrawal.objects.filter(user=w.user)
                            )
                            net_contrib = deposits_sum - withdrawals_sum
                            pnl = user_value - net_contrib
                            if pnl > 0:
                                pnl_color = "#23c4a9"
                            elif pnl < 0:
                                pnl_color = "#ff7a7a"
                    except Exception:
                        pnl = 0.0
                        pnl_color = "gray"
                except Exception:
                    user_shares = 0.0
                    user_value = 0.0
                    ftc_balance = None
                    xrp_balance = None

            # Active loans count (created/funded/disbursed)
            active_count = Loan.objects.filter(
                state__in=["created", "funded", "disbursed"]
            ).count()

            # Build private key input field based on whether code is present
            # When code is present, show masked value but allow manual override
            if code and key_masked:
                private_key_input = f'<input type="password" name="private_key" placeholder="0x..." value="{key_masked}" required style="font-family: monospace; letter-spacing: 2px;" />'
                private_key_help = '<div style="margin-top:4px; font-size:11px; color:var(--muted);">Auto-filled via secure code (masked). Full key retrieved from secure storage. You can override by entering a different key.</div>'
            else:
                private_key_input = '<input type="password" name="private_key" placeholder="0x..." required />'
                private_key_help = ''

            html = f"""
                <html>
                    <head>
                        <title>Nkadime – FTCT Deposits</title>
                        <meta name="viewport" content="width=device-width, initial-scale=1" />
                        <style>
                            :root {{
                                --bg: #0b1020; /* deep navy */
                                --panel: #121a33; /* card */
                                --panel-2: #0f1530;
                                --text: #e9edf5;
                                --muted: #a6b0c3;
                                --primary: #6c9cff;
                                --accent: #23c4a9;
                                --warn: #ffcc66;
                                --danger: #ff7a7a;
                                --shadow: 0 10px 30px rgba(0,0,0,0.35);
                            }}
                            * {{ box-sizing: border-box; }}
                            body {{
                                margin: 0;
                                font-family: -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', Arial, 'Noto Sans', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol';
                                background: radial-gradient(1200px 800px at 10% -10%, #1a2455, transparent),
                                            radial-gradient(1000px 600px at 110% 10%, #0f5b6b, transparent),
                                            var(--bg);
                                color: var(--text);
                                min-height: 100vh;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                padding: 24px;
                            }}
                            .shell {{
                                width: 100%;
                                max-width: 1040px;
                                display: grid;
                                grid-template-columns: 1.1fr 1fr;
                                gap: 24px;
                            }}
                            @media (max-width: 980px) {{
                                .shell {{ grid-template-columns: 1fr; }}
                            }}
                            .card {{
                                background: linear-gradient(180deg, var(--panel), var(--panel-2));
                                border: 1px solid rgba(255,255,255,0.06);
                                border-radius: 16px;
                                box-shadow: var(--shadow);
                                padding: 24px;
                            }}
                            .heading h1 {{
                                font-size: 28px;
                                margin: 0 0 6px 0;
                                letter-spacing: 0.2px;
                            }}
                            .heading p {{ color: var(--muted); margin: 0; }}
                            .metrics {{
                                display: grid;
                                grid-template-columns: repeat(2, 1fr);
                                gap: 16px;
                                margin-top: 16px;
                            }}
                            .metric {{
                                background: rgba(255,255,255,0.04);
                                border: 1px solid rgba(255,255,255,0.06);
                                border-radius: 12px;
                                padding: 16px;
                            }}
                            .metric .label {{ color: var(--muted); font-size: 12px; }}
                            .metric .value {{ font-size: 22px; margin-top: 6px; }}
                            .note {{
                                margin-top: 12px;
                                padding: 12px 14px;
                                border-radius: 10px;
                                background: rgba(35, 196, 169, 0.1);
                                border: 1px solid rgba(35, 196, 169, 0.25);
                                color: #bff5ea;
                                font-size: 13px;
                            }}
                            form label {{ display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }}
                            .field {{ margin-bottom: 14px; }}
                            input[type="text"], input[type="number"], input[type="password"] {{
                                width: 100%;
                                padding: 12px 14px;
                                border-radius: 10px;
                                border: 1px solid rgba(255,255,255,0.08);
                                background: rgba(255,255,255,0.06);
                                color: var(--text);
                                outline: none;
                            }}
                            input::placeholder {{ color: rgba(255,255,255,0.45); }}
                            .field-with-hidden {{ position: relative; }}
                            .field-with-hidden input[type="password"] {{
                                font-family: monospace;
                                letter-spacing: 2px;
                            }}
                            .hidden-key {{ display: none; }}
                            .btn {{
                                display: inline-flex;
                                gap: 8px;
                                align-items: center;
                                border: 0;
                                background: linear-gradient(90deg, var(--primary), #8ab4ff);
                                color: #071126;
                                padding: 12px 16px;
                                border-radius: 10px;
                                font-weight: 600;
                                cursor: pointer;
                                box-shadow: 0 6px 18px rgba(108,156,255,0.35);
                            }}
                            .muted {{ color: var(--muted); }}
                            .hr {{ height: 1px; background: rgba(255,255,255,0.08); margin: 16px 0; border: 0; }}
                            .list {{ margin: 0; padding-left: 18px; color: var(--muted); }}
                        </style>
                    </head>
                    <body>
                        <div style="position:fixed; top:16px; left:16px; font-weight:700; letter-spacing:0.3px; color:#bcd6ff; background:rgba(108,156,255,0.12); border:1px solid rgba(108,156,255,0.35); padding:6px 10px; border-radius:10px; box-shadow:0 6px 18px rgba(108,156,255,0.2); user-select:none;">Nkadime</div>
                        <div class="shell">
                            <div class="card">
                                <div class="heading">
                                    <h1>Nkadime FTCT Liquidity Pool</h1>
                                    <p>Deposit FTCT to earn a share of pool interest.</p>
                                </div>
                                <div class="metrics">
                                    <div class="metric">
                                        <div class="label">Total Pool</div>
                                        <div class="value">{total_pool:,.2f} FTCT</div>
                                    </div>
                                    <div class="metric">
                                        <div class="label">Total Shares</div>
                                        <div class="value">{total_shares:,.6f}</div>
                                    </div>
                                    <div class="metric">
                                        <div class="label">Active Loans</div>
                                        <div class="value">{active_count}</div>
                                    </div>
                                    <div class="metric">
                                        <div class="label">Your Investment (est.)</div>
                                        <div class="value">{user_value:,.2f} FTCT</div>
                                    </div>
                                    <div class="metric">
                                        <div class="label">Your Shares</div>
                                        <div class="value">{user_shares:,.6f}</div>
                                    </div>
                                    <div class="metric">
                                        <div class="label">Your PnL</div>
                                        <div class="value" style="color:{pnl_color};">{pnl:,.2f} FTCT</div>
                                    </div>
                                </div>
                                <div class="note">These wallet details were prefilled from your Telegram account and can be edited below.</div>
                                <hr class="hr" />
                                <form method="post" id="depositForm">
                                    <input type="hidden" name="code" value="{code}" />
                                    <div class="field">
                                        <label>Wallet Address</label>
                                        <input type="text" name="wallet" placeholder="0x..." value="{wallet_q}" required />
                                    </div>
                                    <div class="field field-with-hidden">
                                        <label>Private Key</label>
                                        {private_key_input}
                                        {private_key_help}
                                    </div>
                                    <div class="field">
                                        <label>Amount (FTCT)</label>
                                        <input type="number" step="0.000001" min="0" name="amount" placeholder="Amount" required />
                                    </div>
                                    <button class="btn" type="submit">💸 Deposit</button>
                                </form>
                                <div class="muted" style="margin-top:12px; font-size:12px;">Ensure you have approved the LoanSystem to spend FTCT (this page will handle approval automatically).</div>
                            </div>
                            <div class="card">
                                <h2 style="margin-top:0;">Your Wallet</h2>
                                <div class="metrics" style="grid-template-columns: 1fr 1fr;">
                                    <div class="metric">
                                        <div class="label">XRP (gas)</div>
                                        <div class="value">{(xrp_balance if xrp_balance is not None else 0):,.6f}</div>
                                    </div>
                                    <div class="metric">
                                        <div class="label">FTCT Balance</div>
                                        <div class="value">{(ftc_balance if ftc_balance is not None else 0):,.2f}</div>
                                    </div>
                                </div>
                                <div class="note" style="margin-top:16px;">You can only deposit up to your FTCT balance. Ensure you also have enough XRP for gas.</div>
                                <h2 style="margin-top:20px;">How deposits work</h2>
                                <ul class="list">
                                    <li>Deposits mint pool shares proportional to your contribution.</li>
                                    <li>As loans earn interest, each share’s value increases.</li>
                                    <li>You can withdraw later by redeeming shares for FTCT (subject to liquidity).</li>
                                </ul>
                                <div class="note" style="margin-top:16px;">Your private key is securely stored. This page uses a one-time code that expires after 15 minutes.</div>
                            </div>
                        </div>
                    </body>
                </html>
            """
            return HttpResponse(html)

        elif request.method == "POST":
            print("POST data:", request.POST)
            
            # Get code from POST data
            code = request.POST.get("code", "").strip()
            
            # Retrieve wallet and private key from Redis using code (one-time use)
            wallet = ""
            private_key = ""
            code_valid = False
            if code:
                code_service = DepositCodeService()
                wallet_data = code_service.get_and_delete(code)
                if wallet_data:
                    wallet = wallet_data.get("wallet", "").strip()
                    private_key = wallet_data.get("private_key", "").strip()
                    code_valid = True
            
            # If code retrieval failed, fall back to POST values (manual entry)
            wallet_post = request.POST.get("wallet", "").strip()
            private_key_post = request.POST.get("private_key", "").strip()
            
            # Use POST values only if code retrieval failed
            if not wallet:
                wallet = wallet_post
            if not private_key:
                private_key = private_key_post
            
            amount_str = request.POST.get("amount", "0").strip()

            # Validate inputs
            if not is_valid_wallet(wallet):
                return HttpResponse(
                    f"<h3>Invalid wallet address: {wallet}</h3><a href=''>Go back</a>"
                )

            if not private_key:
                if code:
                    return HttpResponse(
                        "<h3>Invalid or expired deposit code. Please generate a new code from Telegram.</h3><a href=''>Go back</a>"
                    )
                return HttpResponse(
                    "<h3>Private key missing</h3><a href=''>Go back</a>"
                )

            try:
                amount = float(amount_str)
                if amount <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError as e:
                return HttpResponse(
                    f"<h3>Invalid amount: {amount_str} ({e})</h3><a href=''>Go back</a>"
                )

            # Kick work to scoring worker and wait briefly for result
            # Validate funds before enqueueing
            try:
                ftc_service = FTCTokenService()
                available_ftc = float(ftc_service.get_balance(wallet))
                if float(amount) > available_ftc:
                    return HttpResponse(
                        f"""
                        <html>
                            <head><title>Nkadime – FTCT Deposits</title></head>
                            <body style='font-family: -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial; background:#0b1020; color:#e9edf5; display:flex; align-items:center; justify-content:center; min-height:100vh;'>
                                <div style='background:#0f1530; border:1px solid rgba(255,255,255,0.07); border-radius:16px; padding:24px; max-width:640px;'>
                                    <h2 style='margin:0 0 10px 0;'>❌ Insufficient FTCT Balance</h2>
                                    <div style='opacity:0.85;'>You tried to deposit <b>{float(amount):,.2f} FTCT</b> but your available balance is <b>{available_ftc:,.2f} FTCT</b>.</div>
                                    <a href='' style='display:inline-block; margin-top:16px; background:linear-gradient(90deg,#6c9cff,#8ab4ff); color:#071126; padding:10px 14px; border-radius:10px; font-weight:600; text-decoration:none;'>Go back</a>
                                </div>
                            </body>
                        </html>
                    """
                    )
            except Exception:
                pass

            # Start async task and return loading page immediately
            try:
                task = process_deposit_ftct.apply_async(
                    args=[wallet, private_key, float(amount)],
                )
                task_id = task.id
                
                # Initialize status store (task will update it as it progresses)
                status_store = DepositStatusStore()
                status_store.create(task_id, wallet, float(amount))
            except Exception as e:
                return HttpResponse(
                    f"<h3>Failed to start deposit: {e}</h3><a href=''>Go back</a>"
                )

            # Return beautiful loading page that polls for status
            loading_html = f"""
                <!DOCTYPE html>
                <html>
                    <head>
                        <title>Nkadime – Processing Deposit</title>
                        <meta name="viewport" content="width=device-width, initial-scale=1" />
                        <style>
                            :root {{
                                --bg: #0b1020;
                                --panel: #121a33;
                                --panel-2: #0f1530;
                                --text: #e9edf5;
                                --muted: #a6b0c3;
                                --primary: #6c9cff;
                                --accent: #23c4a9;
                                --warn: #ffcc66;
                                --danger: #ff7a7a;
                            }}
                            * {{ box-sizing: border-box; }}
                            body {{
                                margin: 0;
                                font-family: -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', Arial;
                                background: radial-gradient(1200px 800px at 10% -10%, #1a2455, transparent),
                                            radial-gradient(1000px 600px at 110% 10%, #0f5b6b, transparent),
                                            var(--bg);
                                color: var(--text);
                                min-height: 100vh;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                padding: 24px;
                            }}
                            .container {{
                                background: linear-gradient(180deg, var(--panel), var(--panel-2));
                                border: 1px solid rgba(255,255,255,0.06);
                                border-radius: 16px;
                                box-shadow: 0 10px 30px rgba(0,0,0,0.35);
                                padding: 40px;
                                max-width: 600px;
                                width: 100%;
                                text-align: center;
                            }}
                            .logo {{
                                position: fixed;
                                top: 16px;
                                left: 16px;
                                font-weight: 700;
                                letter-spacing: 0.3px;
                                color: #bcd6ff;
                                background: rgba(108,156,255,0.12);
                                border: 1px solid rgba(108,156,255,0.35);
                                padding: 6px 10px;
                                border-radius: 10px;
                                box-shadow: 0 6px 18px rgba(108,156,255,0.2);
                                user-select: none;
                            }}
                            h1 {{
                                margin: 0 0 16px 0;
                                font-size: 32px;
                                background: linear-gradient(90deg, var(--primary), var(--accent));
                                -webkit-background-clip: text;
                                -webkit-text-fill-color: transparent;
                                background-clip: text;
                            }}
                            .spinner-container {{
                                margin: 32px 0;
                            }}
                            .spinner {{
                                width: 80px;
                                height: 80px;
                                margin: 0 auto;
                                position: relative;
                            }}
                            .spinner-ring {{
                                position: absolute;
                                width: 100%;
                                height: 100%;
                                border: 4px solid rgba(108,156,255,0.2);
                                border-top-color: var(--primary);
                                border-radius: 50%;
                                animation: spin 1s linear infinite;
                            }}
                            .spinner-ring:nth-child(2) {{
                                width: 70%;
                                height: 70%;
                                top: 15%;
                                left: 15%;
                                border-color: rgba(35,196,169,0.2);
                                border-top-color: var(--accent);
                                animation-duration: 1.5s;
                                animation-direction: reverse;
                            }}
                            @keyframes spin {{
                                to {{ transform: rotate(360deg); }}
                            }}
                            .status-text {{
                                font-size: 18px;
                                color: var(--muted);
                                margin: 24px 0;
                                min-height: 24px;
                            }}
                            .step {{
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                gap: 12px;
                                margin: 12px 0;
                                padding: 12px;
                                background: rgba(255,255,255,0.03);
                                border-radius: 10px;
                                opacity: 0.5;
                                transition: opacity 0.3s;
                            }}
                            .step.active {{
                                opacity: 1;
                                background: rgba(108,156,255,0.1);
                            }}
                            .step.complete {{
                                opacity: 1;
                                background: rgba(35,196,169,0.1);
                            }}
                            .step-icon {{
                                font-size: 20px;
                            }}
                            .info-box {{
                                margin-top: 32px;
                                padding: 16px;
                                background: rgba(35,196,169,0.1);
                                border: 1px solid rgba(35,196,169,0.25);
                                border-radius: 12px;
                                color: #bff5ea;
                                font-size: 14px;
                                text-align: left;
                            }}
                            .info-box strong {{
                                display: block;
                                margin-bottom: 8px;
                                color: #fff;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="logo">Nkadime</div>
                        <div class="container">
                            <h1>Processing Deposit</h1>
                            <div class="spinner-container">
                                <div class="spinner">
                                    <div class="spinner-ring"></div>
                                    <div class="spinner-ring"></div>
                                </div>
                            </div>
                            <div class="status-text" id="statusText">Initializing transaction...</div>
                            <div id="steps">
                                <div class="step" id="step-approve">
                                    <span class="step-icon">⏳</span>
                                    <span>Approving FTCT spending</span>
                                </div>
                                <div class="step" id="step-deposit">
                                    <span class="step-icon">⏳</span>
                                    <span>Depositing to pool</span>
                                </div>
                                <div class="step" id="step-confirm">
                                    <span class="step-icon">⏳</span>
                                    <span>Confirming on blockchain</span>
                                </div>
                            </div>
                            <div class="info-box">
                                <strong>💡 Tip:</strong>
                                You can withdraw your funds anytime using the <code>/withdraw</code> command in Telegram.
                                The withdrawal will redeem your pool shares for FTCT.
                            </div>
                        </div>
                        <script>
                            const taskId = '{task_id}';
                            const amount = {float(amount)};
                            let pollCount = 0;
                            const maxPolls = 120; // 2 minutes max
                            
                            function updateStatus(response) {{
                                const statusEl = document.getElementById('statusText');
                                const status = response.status || 'PENDING';
                                const stage = response.stage || 'initializing';
                                
                                if (status === 'success') {{
                                    statusEl.textContent = '✅ Deposit successful!';
                                    statusEl.style.color = 'var(--accent)';
                                    const result = response.result || {{}};
                                    showSuccess(result);
                                }} else if (status === 'error') {{
                                    statusEl.textContent = '❌ Deposit failed';
                                    statusEl.style.color = 'var(--danger)';
                                    showError(response.error || 'Unknown error');
                                }} else {{
                                    // Show status based on stage
                                    const statusMessages = {{
                                        'initializing': 'Initializing transaction...',
                                        'approving': 'Waiting for approval transaction...',
                                        'depositing': 'Waiting for deposit transaction...',
                                        'confirming': 'Confirming on blockchain...',
                                    }};
                                    statusEl.textContent = statusMessages[stage] || 'Processing... (' + (pollCount * 2) + 's)';
                                    
                                    // Update steps based on actual stage
                                    updateSteps(stage, response);
                                }}
                            }}
                            
                            function updateSteps(stage, response) {{
                                const stages = {{
                                    'initializing': 0,
                                    'approving': 0,
                                    'depositing': 1,
                                    'confirming': 2,
                                }};
                                const currentStageIndex = stages[stage] || 0;
                                const steps = ['approve', 'deposit', 'confirm'];
                                
                                steps.forEach((s, i) => {{
                                    const el = document.getElementById('step-' + s);
                                    const stepText = el.querySelector('span:last-child');
                                    
                                    // Check transaction status if available
                                    let isComplete = i < currentStageIndex;
                                    let isActive = i === currentStageIndex;
                                    
                                    if (s === 'approve' && response.approve_tx_hash) {{
                                        const txShort = response.approve_tx_hash.substring(0, 10);
                                        stepText.innerHTML = `Approving FTCT <span style="font-size:11px; color:var(--muted);">(${{txShort}}...)</span>`;
                                        if (response.approve_tx_status === 'confirmed') {{
                                            isComplete = true;
                                            isActive = false;
                                        }} else if (response.approve_tx_status === 'failed') {{
                                            el.querySelector('.step-icon').textContent = '❌';
                                            el.style.background = 'rgba(255,122,122,0.1)';
                                        }}
                                    }}
                                    
                                    if (s === 'deposit' && response.deposit_tx_hash) {{
                                        const txShort = response.deposit_tx_hash.substring(0, 10);
                                        stepText.innerHTML = `Depositing to pool <span style="font-size:11px; color:var(--muted);">(${{txShort}}...)</span>`;
                                        if (response.deposit_tx_status === 'confirmed') {{
                                            isComplete = true;
                                            isActive = false;
                                        }} else if (response.deposit_tx_status === 'failed') {{
                                            el.querySelector('.step-icon').textContent = '❌';
                                            el.style.background = 'rgba(255,122,122,0.1)';
                                        }}
                                    }}
                                    
                                    if (isComplete) {{
                                        el.classList.add('complete');
                                        el.classList.remove('active');
                                        el.querySelector('.step-icon').textContent = '✅';
                                    }} else if (isActive) {{
                                        el.classList.add('active');
                                        el.classList.remove('complete');
                                        el.querySelector('.step-icon').textContent = '⏳';
                                    }} else {{
                                        el.classList.remove('active', 'complete');
                                        el.querySelector('.step-icon').textContent = '⏳';
                                    }}
                                }});
                            }}
                            
                            function showSuccess(data) {{
                                const container = document.querySelector('.container');
                                container.innerHTML = `
                                    <h1>Deposit Successful!</h1>
                                    <div style="margin: 24px 0; font-size: 18px; color: var(--accent);">
                                        Deposited R{{amount.toFixed(2)}} FTCT
                                    </div>
                                    <div style="margin: 24px 0; font-size: 14px; color: var(--muted);">
                                        Feel free to close this page, and to make another deposit please use the /deposit command in Telegram.
                                    </div>
                                    <div style="background: rgba(255,255,255,0.04); border-radius: 12px; padding: 20px; margin: 20px 0; text-align: left;">
                                        <div style="margin: 8px 0;"><strong>Approve TX:</strong> <code>${{data.approve_tx_hash || 'N/A'}}</code></div>
                                        <div style="margin: 8px 0;"><strong>Deposit TX:</strong> <code>${{data.deposit_tx_hash || 'N/A'}}</code></div>
                                        <div style="margin: 16px 0 8px 0;"><strong>Your Shares:</strong> ${{data.user_shares?.toFixed(6) || '0'}}</div>
                                        <div style="margin: 8px 0;"><strong>Your Investment:</strong> ${{data.user_value?.toFixed(2) || '0'}} FTCT</div>
                                    </div>
                                    <div class="info-box">
                                        <strong>💡 Withdraw Funds:</strong>
                                        Use the <code>/withdraw</code> command in Telegram to withdraw your funds anytime.
                                    </div>
                                `;
                            }}
                            
                            function showError(error) {{
                                const container = document.querySelector('.container');
                                container.innerHTML = `
                                    <h1 style="background:linear-gradient(90deg,var(--danger),#ff9a9a); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">❌ Deposit Failed</h1>
                                    <div style="margin: 24px 0; padding: 16px; background:rgba(255,122,122,0.1); border:1px solid rgba(255,122,122,0.3); border-radius:12px; color: #ffcccc;">
                                        ${{error || 'An error occurred during the deposit process.'}}
                                    </div>
                                    <a href="" style="display:inline-block; margin-top:20px; background:linear-gradient(90deg,var(--primary),#8ab4ff); color:#071126; padding:12px 24px; border-radius:10px; font-weight:600; text-decoration:none;">↩️ Go Back</a>
                                `;
                            }}
                            
                            async function checkStatus() {{
                                pollCount++;
                                if (pollCount > maxPolls) {{
                                    showError('Request timed out. Please check your transaction on the blockchain.');
                                    return;
                                }}
                                
                                try {{
                                    const response = await fetch('/deposit_ftct/status/' + taskId);
                                    const data = await response.json();
                                    
                                    // Use new status format
                                    updateStatus(data);
                                    
                                    if (data.status === 'success' || data.status === 'error') {{
                                        // Stop polling on completion
                                    }} else {{
                                        // Continue polling
                                        setTimeout(checkStatus, 2000);
                                    }}
                                }} catch (error) {{
                                    console.error('Status check error:', error);
                                    setTimeout(checkStatus, 2000);
                                }}
                            }}
                            
                            // Start polling
                            checkStatus();
                        </script>
                    </body>
                </html>
            """
            return HttpResponse(loading_html)

        else:
            return HttpResponse("<h3>Invalid request</h3><a href=''>Go back</a>")

    except Exception as e:
        return HttpResponse(
            f"<h3>Unexpected server error: {e}</h3><a href=''>Go back</a>"
        )


@csrf_exempt
def deposit_status_view(request, task_id: str):
    """Check the status of a deposit task and blockchain transactions."""
    try:
        status_store = DepositStatusStore()
        status_data = status_store.get(task_id)
        
        if not status_data:
            # Fallback to Celery result if status store not found
            result = AsyncResult(task_id, app=app)
            if result.ready():
                if result.successful():
                    return JsonResponse({
                        'status': 'SUCCESS',
                        'result': result.result,
                        'stage': 'completed'
                    })
                else:
                    return JsonResponse({
                        'status': 'FAILURE',
                        'error': str(result.info) if result.info else 'Task failed',
                        'stage': 'error'
                    })
            else:
                return JsonResponse({
                    'status': 'PENDING',
                    'stage': 'processing',
                    'state': result.state
                })
        
        # Use status store data (includes blockchain transaction status)
        response_data = {
            'status': status_data.get('status', 'pending'),
            'stage': status_data.get('stage', 'initializing'),
            'approve_tx_hash': status_data.get('approve_tx_hash'),
            'approve_tx_status': status_data.get('approve_tx_status'),
            'deposit_tx_hash': status_data.get('deposit_tx_hash'),
            'deposit_tx_status': status_data.get('deposit_tx_status'),
        }
        
        # Include result data if successful
        if status_data.get('status') == 'success':
            response_data['result'] = {
                'approve_tx_hash': status_data.get('approve_tx_hash'),
                'deposit_tx_hash': status_data.get('deposit_tx_hash'),
                'before_pool': status_data.get('before_pool'),
                'before_shares': status_data.get('before_shares'),
                'after_pool': status_data.get('after_pool'),
                'after_shares': status_data.get('after_shares'),
                'user_shares': status_data.get('user_shares'),
                'user_value': status_data.get('user_value'),
            }
        # Include error if failed
        if status_data.get('status') == 'error':
            response_data['error'] = status_data.get('error', 'Unknown error')
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'FAILURE',
            'error': str(e),
            'stage': 'error'
        }, status=500)
