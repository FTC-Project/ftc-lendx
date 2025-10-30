from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from web3 import Web3
from django.conf import settings
from backend.apps.tokens.services.loan_system import LoanSystemService
from backend.apps.tokens.services.ftc_token import FTCTokenService

# Simple Ethereum wallet validation
def is_valid_wallet(wallet):
    return True

@csrf_exempt  # for testing only; remove in production
def deposit_ftct_view(request):
    try:
        if request.method == 'GET':
            # Show single-page form
            return HttpResponse("""
                <html>
                    <head>
                        <style>
                            body {
                                display: flex;
                                flex-direction: column;
                                justify-content: center;
                                align-items: center;
                                height: 100vh;
                                margin: 0;
                                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                                background-color: #f4f6f8;
                            }
                            .heading {
                                margin-bottom: 20px;
                                text-align: center;
                            }
                            .heading h1 {
                                font-size: 32px;
                                color: #2c3e50;
                                margin: 0;
                            }
                            .container {
                                background: white;
                                padding: 40px;
                                border-radius: 12px;
                                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                                text-align: center;
                                max-width: 500px;
                                width: 100%;
                            }
                            h2 {
                                color: #2c3e50;
                                margin-bottom: 30px;
                            }
                            input {
                                padding: 12px;
                                width: 100%;
                                font-size: 16px;
                                margin-bottom: 20px;
                                border: 1px solid #ccc;
                                border-radius: 6px;
                            }
                            button {
                                padding: 12px 24px;
                                font-size: 16px;
                                background-color: #3498db;
                                color: white;
                                border: none;
                                border-radius: 6px;
                                cursor: pointer;
                            }
                            button:hover {
                                background-color: #2980b9;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="heading">
                            <h1>Ndikame Lending Page</h1>
                        </div>
                        <div class="container">
                            <h2>💸 Deposit FTCT</h2>
                            <form method="post">
                                <input type="text" name="wallet" placeholder="Wallet Address (0x...)" required>
                                <input type="text" name="private_key" placeholder="Private Key" required>
                                <input type="number" name="amount" placeholder="Amount" required>
                                <button type="submit">Deposit</button>
                            </form>
                        </div>
                    </body>
                </html>
            """)


        elif request.method == 'POST':
            print("POST data:", request.POST)
            wallet = request.POST.get('wallet', '').strip()
            #wallet = Web3.to_checksum_address(wallet)
            print("Wallet value:", wallet)

            private_key = request.POST.get('private_key', '').strip()
            amount_str = request.POST.get('amount', '0').strip()

            # Validate inputs
            if not is_valid_wallet(wallet):
                return HttpResponse(f"<h3>Invalid wallet address: {wallet}</h3><a href=''>Go back</a>")

            if not private_key:
                return HttpResponse("<h3>Private key missing</h3><a href=''>Go back</a>")

            try:
                amount = float(amount_str)
                if amount <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError as e:
                return HttpResponse(f"<h3>Invalid amount: {amount_str} ({e})</h3><a href=''>Go back</a>")

            # Call LoanSystemService
            try:
                # Initialize services
                ftc_service = FTCTokenService()
                loan_service = LoanSystemService()

                # Step 1: Approve LoanSystem contract to spend FTCT
                approve_tx = ftc_service.approve(
                    wallet,
                    settings.LOANSYSTEM_ADDRESS,
                    amount,
                    private_key
                )

                # Step 2: Deposit into pool
                result = loan_service.deposit_ftct(
                    lender_address=wallet,
                    amount=amount,
                    lender_private_key=private_key
                )

                shares = loan_service.get_shares_of(wallet)

            except Exception as e:
                return HttpResponse(f"<h3>Deposit failed: {e}</h3><a href=''>Go back</a>")

            # Success page
            return HttpResponse(f"""
                <html>
                    <head>
                        <style>
                            body {{
                                display: flex;
                                justify-content: center;
                                align-items: center;
                                height: 100vh;
                                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                                background-color: #f4f6f8;
                                margin: 0;
                            }}
                            .container {{
                                background: white;
                                padding: 40px;
                                border-radius: 12px;
                                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                                text-align: center;
                                max-width: 500px;
                            }}
                            h2 {{
                                color: #2c3e50;
                                margin-bottom: 20px;
                            }}
                            p {{
                                font-size: 16px;
                                margin: 10px 0;
                                color: #34495e;
                            }}
                            b {{
                                color: #2c3e50;
                            }}
                            a {{
                                display: inline-block;
                                margin-top: 20px;
                                text-decoration: none;
                                color: #3498db;
                                font-weight: bold;
                            }}
                            a:hover {{
                                text-decoration: underline;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h2>✅ Deposit Successful</h2>
                            <p>Deposit transaction hash:<br><b>{result.get('tx_hash', 'N/A')}</b></p>
                            <p>Total Lender Shares:<br><b>{shares}</b></p>
                            <a href=''>🔁 Start Over</a>
                        </div>
                    </body>
                </html>
            """)

        else:
            return HttpResponse("<h3>Invalid request</h3><a href=''>Go back</a>")

    except Exception as e:
        return HttpResponse(f"<h3>Unexpected server error: {e}</h3><a href=''>Go back</a>")
