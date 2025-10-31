from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from web3 import Web3
from django.conf import settings
from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.tokens.services.ftc_token import FTCTokenService
from backend.apps.loans.models import Loan
from backend.apps.sys_frontend.tasks import process_deposit_ftct
from backend.apps.pool.models import PoolDeposit, PoolWithdrawal
from backend.apps.users.models import Wallet


# Simple Ethereum wallet validation
def is_valid_wallet(wallet):
    return True


@csrf_exempt  # for testing only; remove in production
def deposit_ftct_view(request):
    try:
        if request.method == "GET":
            # Prefill from query params
            wallet_q = (request.GET.get("wallet") or "").strip()
            key_q = (request.GET.get("private_key") or "").strip()

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
                            input[type="text"], input[type="number"] {{
                                width: 100%;
                                padding: 12px 14px;
                                border-radius: 10px;
                                border: 1px solid rgba(255,255,255,0.08);
                                background: rgba(255,255,255,0.06);
                                color: var(--text);
                                outline: none;
                            }}
                            input::placeholder {{ color: rgba(255,255,255,0.45); }}
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
                                <form method="post">
                                    <div class="field">
                                        <label>Wallet Address</label>
                                        <input type="text" name="wallet" placeholder="0x..." value="{wallet_q}" required />
                                    </div>
                                    <div class="field">
                                        <label>Private Key</label>
                                        <input type="text" name="private_key" placeholder="0x..." value="{key_q}" required />
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
                                <div class="note" style="margin-top:16px;">Never share your private key publicly. It is shown here because you arrived from a trusted in-bot link.</div>
                            </div>
                        </div>
                    </body>
                </html>
            """
            return HttpResponse(html)

        elif request.method == "POST":
            print("POST data:", request.POST)
            wallet = request.POST.get("wallet", "").strip()
            # wallet = Web3.to_checksum_address(wallet)
            print("Wallet value:", wallet)

            private_key = request.POST.get("private_key", "").strip()
            amount_str = request.POST.get("amount", "0").strip()

            # Validate inputs
            if not is_valid_wallet(wallet):
                return HttpResponse(
                    f"<h3>Invalid wallet address: {wallet}</h3><a href=''>Go back</a>"
                )

            if not private_key:
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

            try:
                result = process_deposit_ftct.apply_async(
                    args=[wallet, private_key, float(amount)],
                ).get(timeout=180)
            except Exception as e:
                return HttpResponse(
                    f"<h3>Deposit failed: {e}</h3><a href=''>Go back</a>"
                )

            approve_tx_hash = result.get("approve_tx_hash")
            deposit_tx_hash = result.get("deposit_tx_hash")
            # Backward/defensive fallback if structure changes
            if not approve_tx_hash:
                atx = result.get("approve_tx", {})
                approve_tx_hash = atx.get("tx_hash") if isinstance(atx, dict) else atx
            if not deposit_tx_hash:
                dtx = result.get("deposit_tx", {})
                deposit_tx_hash = dtx.get("tx_hash") if isinstance(dtx, dict) else dtx
            before_pool = result.get("before_pool")
            before_shares = result.get("before_shares")
            after_pool = result.get("after_pool")
            after_shares = result.get("after_shares")
            user_shares = result.get("user_shares")
            user_value = result.get("user_value")

            # Success page with before/after
            return HttpResponse(
                f"""
                <html>
                    <head>
                        <title>Nkadime – FTCT Deposits</title>
                        <style>
                            body {{ margin:0; background:#0b1020; color:#e9edf5; font-family: -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', Arial; display:flex; align-items:center; justify-content:center; min-height:100vh; }}
                            .container {{ background:#0f1530; border:1px solid rgba(255,255,255,0.07); border-radius:16px; padding:28px; width:100%; max-width:780px; box-shadow: 0 10px 30px rgba(0,0,0,0.35); }}
                            h2 {{ margin:0 0 8px 0; }}
                            .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:16px; }}
                            .card {{ background: rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); padding:16px; border-radius:12px; }}
                            .label {{ color:#a6b0c3; font-size:12px; }}
                            .value {{ font-size:20px; margin-top:6px; }}
                            .tx {{ margin-top: 12px; font-size:14px; }}
                            .btn {{ display:inline-block; background:linear-gradient(90deg,#6c9cff,#8ab4ff); color:#071126; padding:12px 16px; border-radius:10px; font-weight:600; text-decoration:none; margin-top:16px; }}
                        </style>
                    </head>
                    <body>
                        <div style="position:fixed; top:16px; left:16px; font-weight:700; letter-spacing:0.3px; color:#bcd6ff; background:rgba(108,156,255,0.12); border:1px solid rgba(108,156,255,0.35); padding:6px 10px; border-radius:10px; box-shadow:0 6px 18px rgba(108,156,255,0.2); user-select:none;">Nkadime</div>
                        <div class="container">
                            <h2>✅ Deposit Successful</h2>
                            <div class="tx">Approve: <b>{approve_tx_hash or 'N/A'}</b></div>
                            <div class="tx">Deposit: <b>{deposit_tx_hash or 'N/A'}</b></div>
                            <div class="grid">
                                <div class="card">
                                    <div class="label">Pool Before</div>
                                    <div class="value">{(before_pool if before_pool is not None else 0):,.2f} FTCT</div>
                                    <div class="label" style="margin-top:10px;">Total Shares Before</div>
                                    <div class="value">{(before_shares if before_shares is not None else 0):,.6f}</div>
                                </div>
                                <div class="card">
                                    <div class="label">Pool After</div>
                                    <div class="value">{after_pool:,.2f} FTCT</div>
                                    <div class="label" style="margin-top:10px;">Total Shares After</div>
                                    <div class="value">{after_shares:,.6f}</div>
                                </div>
                            </div>
                            <div class="grid" style="margin-top:16px;">
                                <div class="card">
                                    <div class="label">Your Shares</div>
                                    <div class="value">{user_shares:,.6f}</div>
                                </div>
                                <div class="card">
                                    <div class="label">Your Investment (est.)</div>
                                    <div class="value">{user_value:,.2f} FTCT</div>
                                </div>
                            </div>
                            <a class="btn" href=''>🔁 Make another deposit</a>
                        </div>
                    </body>
                </html>
            """
            )

        else:
            return HttpResponse("<h3>Invalid request</h3><a href=''>Go back</a>")

    except Exception as e:
        return HttpResponse(
            f"<h3>Unexpected server error: {e}</h3><a href=''>Go back</a>"
        )
