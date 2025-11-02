from django.http import HttpResponse


def terms_of_service_view(request):
    """Render the Terms of Service page with beautiful styling matching the deposit page."""
    
    html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Nkadime – Terms of Service</title>
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <style>
                :root {
                    --bg: #0b1020;
                    --panel: #121a33;
                    --panel-2: #0f1530;
                    --text: #e9edf5;
                    --muted: #a6b0c3;
                    --primary: #6c9cff;
                    --accent: #23c4a9;
                    --warn: #ffcc66;
                    --danger: #ff7a7a;
                    --shadow: 0 10px 30px rgba(0,0,0,0.35);
                }
                * { box-sizing: border-box; }
                body {
                    margin: 0;
                    font-family: -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', Arial, 'Noto Sans', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol';
                    background: radial-gradient(1200px 800px at 10% -10%, #1a2455, transparent),
                                radial-gradient(1000px 600px at 110% 10%, #0f5b6b, transparent),
                                var(--bg);
                    color: var(--text);
                    min-height: 100vh;
                    padding: 24px;
                }
                .logo {
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
                }
                .container {
                    max-width: 900px;
                    margin: 0 auto;
                    background: linear-gradient(180deg, var(--panel), var(--panel-2));
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 16px;
                    box-shadow: var(--shadow);
                    padding: 40px;
                }
                h1 {
                    font-size: 36px;
                    margin: 0 0 8px 0;
                    background: linear-gradient(90deg, var(--primary), var(--accent));
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                .subtitle {
                    color: var(--muted);
                    font-size: 16px;
                    margin: 0 0 32px 0;
                }
                h2 {
                    font-size: 24px;
                    margin: 32px 0 16px 0;
                    color: var(--primary);
                    border-bottom: 1px solid rgba(255,255,255,0.1);
                    padding-bottom: 8px;
                }
                h3 {
                    font-size: 18px;
                    margin: 24px 0 12px 0;
                    color: var(--accent);
                }
                p {
                    line-height: 1.7;
                    margin: 12px 0;
                    color: var(--text);
                }
                strong {
                    color: var(--text);
                    font-weight: 600;
                }
                ul, ol {
                    margin: 12px 0;
                    padding-left: 24px;
                    line-height: 1.8;
                }
                li {
                    margin: 8px 0;
                    color: var(--text);
                }
                a {
                    color: var(--primary);
                    text-decoration: none;
                    border-bottom: 1px solid rgba(108,156,255,0.3);
                    transition: border-color 0.2s;
                }
                a:hover {
                    border-color: var(--primary);
                }
                .highlight-box {
                    background: rgba(35,196,169,0.1);
                    border: 1px solid rgba(35,196,169,0.25);
                    border-radius: 12px;
                    padding: 16px;
                    margin: 16px 0;
                    color: #bff5ea;
                }
                .warning-box {
                    background: rgba(255,122,122,0.1);
                    border: 1px solid rgba(255,122,122,0.25);
                    border-radius: 12px;
                    padding: 16px;
                    margin: 16px 0;
                    color: #ffcccc;
                }
                .section {
                    margin: 24px 0;
                }
                .section-number {
                    display: inline-block;
                    background: rgba(108,156,255,0.15);
                    border: 1px solid rgba(108,156,255,0.3);
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 12px;
                    font-weight: 600;
                    color: var(--primary);
                    margin-right: 8px;
                }
                code {
                    background: rgba(255,255,255,0.08);
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-family: 'Courier New', monospace;
                    font-size: 14px;
                    color: var(--accent);
                }
                @media (max-width: 768px) {
                    .container {
                        padding: 24px;
                    }
                    h1 {
                        font-size: 28px;
                    }
                    h2 {
                        font-size: 20px;
                    }
                }
            </style>
        </head>
        <body>
            <div class="logo">Nkadime</div>
            <div class="container">
                <h1>Terms of Service</h1>
                <p class="subtitle">Last updated: November 2025</p>
                
                <div class="section">
                    <h2><span class="section-number">1</span> Acceptance of Terms</h2>
                    <p>By clicking "Accept" when prompted by the Nkadime Telegram bot, you ("User," "you," or "your") agree to be bound by these Terms of Service ("Terms") and acknowledge that you have read, understood, and agree to comply with them. These Terms constitute a legally binding agreement between you and Nkadime ("we," "us," or "our").</p>
                    <div class="warning-box">
                        <strong>If you do not accept these Terms, click "Decline" and do not use our services.</strong>
                    </div>
                </div>

                <div class="section">
                    <h2><span class="section-number">2</span> Eligibility</h2>
                    <p>To use Nkadime, you must:</p>
                    <ul>
                        <li>Be at least 18 years of age</li>
                        <li>Be a resident of South Africa with a valid South African bank account</li>
                        <li>Have the legal capacity to enter into binding contracts</li>
                        <li>Provide accurate and complete information during registration</li>
                        <li>Complete our Know Your Customer (KYC) verification process</li>
                    </ul>
                    <p>By accepting these Terms, you represent and warrant that you meet all eligibility requirements.</p>
                </div>

                <div class="section">
                    <h2><span class="section-number">3</span> Service Description</h2>
                    <p>Nkadime is a decentralized micro-lending platform that:</p>
                    <ul>
                        <li>Connects borrowers and lenders through a Telegram bot interface</li>
                        <li>Calculates alternative credit scores using Open Banking transaction data</li>
                        <li>Facilitates peer-to-peer lending transactions via smart contracts on the XRPL EVM Sidechain</li>
                        <li>Issues loans denominated in FTCoin (FTC), our stablecoin pegged 1:1 with South African Rand (ZAR)</li>
                        <li>Processes repayments via smart contracts</li>
                        <li>Issues non-transferable CreditTrust Tokens based on repayment behavior</li>
                    </ul>
                    <p>All loans are denominated in FTC, where <strong>1 FTC = 1 ZAR</strong>.</p>
                </div>

                <div class="section">
                    <h2><span class="section-number">4</span> User Registration and KYC</h2>
                    
                    <h3>4.1 Registration Process</h3>
                    <p>To access our services, you must:</p>
                    <ol>
                        <li>Initiate registration via the <code>/start</code> command in our Telegram bot</li>
                        <li>Proceed to <code>/register</code> and provide required personal information</li>
                        <li>Complete KYC verification, which may include:
                            <ul>
                                <li>Full legal name</li>
                                <li>South African ID number</li>
                                <li>Proof of address</li>
                                <li>Bank account details</li>
                                <li>Selfie verification</li>
                                <li>Consent to access banking transaction data via Open Banking APIs</li>
                            </ul>
                        </li>
                    </ol>

                    <h3>4.2 Information Accuracy</h3>
                    <p>You agree to provide accurate, current, and complete information during registration and to update such information promptly if it changes. Providing false or misleading information constitutes a material breach of these Terms and may result in immediate termination of your account.</p>

                    <h3>4.3 Account Security</h3>
                    <p>You are responsible for:</p>
                    <ul>
                        <li>Maintaining the confidentiality of your Telegram account credentials</li>
                        <li>All activities that occur through your account</li>
                        <li>Notifying us immediately of any unauthorized access or security breach</li>
                    </ul>
                </div>

                <div class="section">
                    <h2><span class="section-number">5</span> Open Banking and Data Access</h2>
                    
                    <h3>5.1 Consent to Data Collection</h3>
                    <p>By accepting these Terms, you explicitly consent to Nkadime accessing your banking transaction data through Absa's Open Banking API or other participating financial institutions. This data will be used solely for:</p>
                    <ul>
                        <li>Calculating your alternative credit score</li>
                        <li>Assessing loan eligibility and terms</li>
                        <li>Monitoring repayment capacity</li>
                        <li>Improving our credit assessment models</li>
                    </ul>

                    <h3>5.2 Data Usage and Retention</h3>
                    <p>We will:</p>
                    <ul>
                        <li>Collect only transaction data necessary for credit assessment</li>
                        <li>Store data securely in compliance with the Protection of Personal Information Act (POPIA)</li>
                        <li>Not sell, rent, or share your banking data with third parties except as required for service delivery or by law</li>
                        <li>Retain your data for the duration of your account plus 7 years as required by South African financial regulations</li>
                    </ul>

                    <h3>5.3 Revocation of Consent</h3>
                    <p>You may revoke consent to data access at any time, but doing so will prevent us from providing services and may affect existing loan obligations.</p>
                </div>

                <div class="section">
                    <h2><span class="section-number">6</span> For Borrowers</h2>
                    
                    <h3>6.1 Loan Application</h3>
                    <p>As a borrower, you may:</p>
                    <ul>
                        <li>Apply for micro-loans through the Telegram bot interface</li>
                        <li>Receive loan offers based on your alternative credit score</li>
                        <li>Accept loan terms including principal amount, interest rate, repayment schedule, and duration</li>
                    </ul>

                    <h3>6.2 Loan Terms</h3>
                    <ul>
                        <li>Loan amounts will be determined based on your credit assessment</li>
                        <li>Interest rates will be disclosed before loan acceptance</li>
                        <li>Repayment schedules will be defined in your loan agreement</li>
                        <li>All loans are issued via smart contracts on the XRPL EVM Sidechain</li>
                        <li>Loan funds will be disbursed in FTC to your designated wallet</li>
                    </ul>

                    <h3>6.3 Repayment Obligations</h3>
                    <p>You agree to:</p>
                    <ul>
                        <li>Repay loans according to the agreed schedule</li>
                        <li>Ensure sufficient FTC balance in your wallet for automated repayment collection</li>
                        <li>Understand that failure to repay will negatively impact your credit score and CreditTrust Token balance</li>
                        <li>Accept that your repayment history will be recorded on the blockchain</li>
                    </ul>

                    <h3>6.4 Default and Collections</h3>
                    <p>In the event of default:</p>
                    <ul>
                        <li>Your CreditTrust Token score will be reduced</li>
                        <li>You will be ineligible for future loans until the default is resolved</li>
                        <li>We may pursue collection activities in accordance with South African law</li>
                        <li>Late fees and penalties may apply as specified in your loan agreement</li>
                        <li>We may report defaults to credit bureaus</li>
                    </ul>
                </div>

                <div class="section">
                    <h2><span class="section-number">7</span> For Lenders</h2>
                    
                    <h3>7.1 Lending Process</h3>
                    <p>As a lender, you may:</p>
                    <ul>
                        <li>Deposit FTC into the liquidity pool via the Telegram bot or web platform</li>
                        <li>Earn interest on funds contributed to the pool</li>
                        <li>Access a secure web dashboard using a one-time password (OTP) sent via Telegram</li>
                        <li>Monitor your lending portfolio and returns</li>
                    </ul>

                    <h3>7.2 Lender Responsibilities</h3>
                    <p>You understand and agree that:</p>
                    <ul>
                        <li>Lending involves risk of borrower default</li>
                        <li>Returns are not guaranteed</li>
                        <li>Your funds will be pooled with other lenders to fund multiple loans</li>
                        <li>Smart contracts will automatically distribute interest payments based on your pool share</li>
                        <li>You may withdraw funds subject to liquidity availability and notice periods</li>
                    </ul>

                    <h3>7.3 Web Platform Access</h3>
                    <ul>
                        <li>OTPs for web platform access will be sent to your registered Telegram account</li>
                        <li>OTPs are valid for a limited time and single use only</li>
                        <li>You must not share your OTP with anyone</li>
                        <li>Web platform access is only available to verified lenders</li>
                    </ul>
                </div>

                <div class="section">
                    <h2><span class="section-number">8</span> FTCoin (FTC) Stablecoin</h2>
                    
                    <h3>8.1 Nature of FTC</h3>
                    <ul>
                        <li>FTC is a stablecoin pegged 1:1 with the South African Rand (ZAR)</li>
                        <li>1 FTC always equals 1 ZAR</li>
                        <li>FTC is issued on the XRPL EVM Sidechain</li>
                        <li>All platform transactions are conducted in FTC</li>
                    </ul>

                    <h3>8.2 Conversion and Transfer</h3>
                    <ul>
                        <li>You may convert ZAR to FTC and vice versa through designated mechanisms</li>
                        <li>Conversion rates will be 1:1 excluding applicable transaction fees</li>
                        <li>Transfer fees on the XRPL network will apply to blockchain transactions</li>
                    </ul>

                    <h3>8.3 Regulatory Status</h3>
                    <p>FTC is a proof-of-concept digital token for educational and experimental purposes. We make no representations regarding:</p>
                    <ul>
                        <li>Regulatory approval or compliance beyond this pilot project</li>
                        <li>Long-term value stability</li>
                        <li>Convertibility or liquidity outside the Nkadime platform</li>
                    </ul>
                </div>

                <div class="section">
                    <h2><span class="section-number">9</span> CreditTrust Tokens</h2>
                    
                    <h3>9.1 Purpose</h3>
                    <p>CreditTrust Tokens are non-transferable reputation tokens that:</p>
                    <ul>
                        <li>Reflect your repayment behavior and creditworthiness</li>
                        <li>Are minted upon successful loan repayments</li>
                        <li>Can be burned (reduced) in cases of late payments or defaults</li>
                        <li>Influence future loan eligibility and terms</li>
                    </ul>

                    <h3>9.2 Non-Transferability</h3>
                    <p>CreditTrust Tokens:</p>
                    <ul>
                        <li>Cannot be sold, traded, or transferred to other users</li>
                        <li>Have no monetary value</li>
                        <li>Serve solely as on-chain reputation indicators within the Nkadime ecosystem</li>
                    </ul>
                </div>

                <div class="section">
                    <h2><span class="section-number">10</span> Smart Contracts and Blockchain</h2>
                    
                    <h3>10.1 Smart Contract Execution</h3>
                    <p>All loans and repayments are governed by smart contracts deployed on the XRPL EVM Sidechain. By using our services, you acknowledge that:</p>
                    <ul>
                        <li>Smart contracts execute automatically based on predefined conditions</li>
                        <li>Transactions on the blockchain are irreversible</li>
                        <li>You are responsible for ensuring adequate wallet balances for automated transactions</li>
                        <li>We are not liable for losses due to smart contract bugs, though we conduct reasonable security audits</li>
                    </ul>

                    <h3>10.2 Gas Fees and Transaction Costs</h3>
                    <p>You are responsible for all blockchain transaction fees (gas fees) associated with:</p>
                    <ul>
                        <li>Loan disbursement</li>
                        <li>Repayment transactions</li>
                        <li>Token transfers</li>
                        <li>Smart contract interactions</li>
                    </ul>
                    <p>These fees are separate from interest rates and platform fees.</p>
                </div>

                <div class="section">
                    <h2><span class="section-number">11</span> Fees and Charges</h2>
                    
                    <h3>11.1 Platform Fees</h3>
                    <p>We may charge:</p>
                    <ul>
                        <li>Origination fees on loans (disclosed before acceptance)</li>
                        <li>Service fees on lender returns (disclosed in lender terms)</li>
                        <li>Late payment fees on overdue loans</li>
                        <li>Early repayment penalties (if applicable, disclosed in loan terms)</li>
                    </ul>

                    <h3>11.2 Fee Disclosure</h3>
                    <p>All fees will be clearly disclosed before you commit to any transaction.</p>
                </div>

                <div class="section">
                    <h2><span class="section-number">12</span> Privacy and Data Protection</h2>
                    
                    <h3>12.1 POPIA Compliance</h3>
                    <p>We comply with South Africa's Protection of Personal Information Act (POPIA) and will:</p>
                    <ul>
                        <li>Process your personal information lawfully and transparently</li>
                        <li>Collect only necessary information</li>
                        <li>Use information only for specified purposes</li>
                        <li>Implement appropriate security measures</li>
                        <li>Allow you to access and correct your information</li>
                    </ul>

                    <h3>12.2 Data Security</h3>
                    <p>While we implement industry-standard security measures, you acknowledge that:</p>
                    <ul>
                        <li>No system is completely secure</li>
                        <li>Blockchain transactions are publicly visible (though pseudonymous)</li>
                        <li>You share responsibility for maintaining account security</li>
                    </ul>

                    <h3>12.3 Privacy Policy</h3>
                    <p>Our separate Privacy Policy, incorporated by reference, provides additional details on data handling. Please review it at [Privacy Policy link].</p>
                </div>

                <div class="section">
                    <h2><span class="section-number">13</span> Prohibited Activities</h2>
                    <p>You agree not to:</p>
                    <ul>
                        <li>Use the service for any illegal purpose or in violation of any laws</li>
                        <li>Provide false, inaccurate, or misleading information</li>
                        <li>Impersonate another person or entity</li>
                        <li>Attempt to manipulate credit scores or game the system</li>
                        <li>Interfere with smart contract operations or blockchain infrastructure</li>
                        <li>Engage in money laundering or terrorist financing</li>
                        <li>Use the service if you are under 18 years of age</li>
                        <li>Share your account credentials or OTPs with others</li>
                        <li>Attempt to reverse engineer, hack, or exploit the platform</li>
                    </ul>
                    <div class="warning-box">
                        <strong>Violation of prohibited activities will result in immediate account termination and may be reported to law enforcement.</strong>
                    </div>
                </div>

                <div class="section">
                    <h2><span class="section-number">14</span> Disclaimers and Limitation of Liability</h2>
                    
                    <h3>14.1 Service Provided "As Is"</h3>
                    <div class="warning-box">
                        <strong>THE NKADIME PLATFORM IS PROVIDED ON AN "AS IS" AND "AS AVAILABLE" BASIS WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT.</strong>
                    </div>

                    <h3>14.2 No Investment Advice</h3>
                    <p>We do not provide financial, investment, legal, or tax advice. You should consult appropriate professionals before making financial decisions.</p>

                    <h3>14.3 Limitation of Liability</h3>
                    <p><strong>TO THE MAXIMUM EXTENT PERMITTED BY LAW, NKADIME, ITS OFFICERS, DIRECTORS, EMPLOYEES, AND AGENTS SHALL NOT BE LIABLE FOR:</strong></p>
                    <ul>
                        <li>Any indirect, incidental, special, consequential, or punitive damages</li>
                        <li>Loss of profits, revenue, data, or use</li>
                        <li>Borrower defaults or lender losses</li>
                        <li>Smart contract failures or blockchain network issues</li>
                        <li>Unauthorized access to your account due to your negligence</li>
                        <li>Third-party actions or services (including banking APIs)</li>
                    </ul>
                    <p><strong>OUR TOTAL LIABILITY SHALL NOT EXCEED THE FEES YOU PAID TO US IN THE 12 MONTHS PRECEDING THE EVENT GIVING RISE TO LIABILITY.</strong></p>

                    <h3>14.4 Experimental Nature</h3>
                    <div class="highlight-box">
                        <p>You acknowledge that Nkadime is a proof-of-concept platform developed for educational purposes as part of an academic class project (ECO5037S 2025). As such:</p>
                        <ul>
                            <li>The platform may contain bugs, errors, or limitations</li>
                            <li>Service continuity beyond the project timeline is not guaranteed</li>
                            <li>Regulatory compliance is limited to the scope of the pilot project</li>
                        </ul>
                    </div>
                </div>

                <div class="section">
                    <h2><span class="section-number">15</span> Indemnification</h2>
                    <p>You agree to indemnify, defend, and hold harmless Nkadime and its affiliates, officers, directors, employees, and agents from any claims, losses, damages, liabilities, and expenses (including legal fees) arising from:</p>
                    <ul>
                        <li>Your violation of these Terms</li>
                        <li>Your violation of any laws or third-party rights</li>
                        <li>Your use or misuse of the platform</li>
                        <li>Inaccurate or false information you provide</li>
                        <li>Your failure to repay loans (for borrowers)</li>
                    </ul>
                </div>

                <div class="section">
                    <h2><span class="section-number">16</span> Dispute Resolution</h2>
                    
                    <h3>16.1 Governing Law</h3>
                    <p>These Terms are governed by the laws of the Republic of South Africa, without regard to conflict of law principles.</p>

                    <h3>16.2 Negotiation</h3>
                    <p>In the event of any dispute, you agree to first attempt good faith negotiation with us for at least 30 days before pursuing formal proceedings.</p>

                    <h3>16.3 Arbitration</h3>
                    <p>If negotiation fails, disputes shall be resolved through binding arbitration under the rules of the Arbitration Foundation of Southern Africa (AFSA), with proceedings held in Cape Town, South Africa.</p>

                    <h3>16.4 Class Action Waiver</h3>
                    <p>You agree to resolve disputes on an individual basis only and waive any right to participate in class action lawsuits or class-wide arbitration.</p>
                </div>

                <div class="section">
                    <h2><span class="section-number">17</span> Termination</h2>
                    
                    <h3>17.1 Your Right to Terminate</h3>
                    <p>You may terminate your account at any time by notifying us through the Telegram bot, provided:</p>
                    <ul>
                        <li>All outstanding loan obligations are fulfilled</li>
                        <li>All pending transactions are completed</li>
                        <li>You have withdrawn all funds from lending pools (subject to notice periods)</li>
                    </ul>

                    <h3>17.2 Our Right to Terminate</h3>
                    <p>We may suspend or terminate your account immediately if:</p>
                    <ul>
                        <li>You violate these Terms</li>
                        <li>You provide false information</li>
                        <li>Your account is used for illegal activities</li>
                        <li>We are required to do so by law</li>
                        <li>We discontinue the service</li>
                    </ul>

                    <h3>17.3 Effect of Termination</h3>
                    <p>Upon termination:</p>
                    <ul>
                        <li>Your access to the platform will be revoked</li>
                        <li>Outstanding loan obligations remain due and payable</li>
                        <li>We will process withdrawal of lending pool funds according to our procedures</li>
                        <li>Your data will be retained as required by law</li>
                    </ul>
                </div>

                <div class="section">
                    <h2><span class="section-number">18</span> Changes to Terms</h2>
                    <p>We reserve the right to modify these Terms at any time. Changes will be effective upon:</p>
                    <ul>
                        <li>Posting updated Terms in the Telegram bot</li>
                        <li>Notifying you via Telegram message</li>
                    </ul>
                    <p>Your continued use of the service after changes constitutes acceptance. If you do not agree to modified Terms, you must stop using the service and terminate your account.</p>
                </div>

                <div class="section">
                    <h2><span class="section-number">19</span> Miscellaneous</h2>
                    
                    <h3>19.1 Entire Agreement</h3>
                    <p>These Terms, together with our Privacy Policy, constitute the entire agreement between you and Nkadime regarding use of the service.</p>

                    <h3>19.2 Severability</h3>
                    <p>If any provision of these Terms is found unenforceable, the remaining provisions will remain in full effect.</p>

                    <h3>19.3 Waiver</h3>
                    <p>Our failure to enforce any provision does not constitute a waiver of that provision or any other provision.</p>

                    <h3>19.4 Assignment</h3>
                    <p>You may not assign or transfer these Terms without our written consent. We may assign these Terms without restriction.</p>

                    <h3>19.5 Language</h3>
                    <p>These Terms are provided in English. In case of conflict between translations, the English version prevails.</p>

                    <h3>19.6 Contact Information</h3>
                    <p>For questions about these Terms, contact us via:</p>
                    <ul>
                        <li>Telegram: @NkadimeSupport</li>
                        <li>Email: <a href="mailto:support@nkadime.co.za">support@nkadime.co.za</a></li>
                    </ul>

                    <h3>19.7 Academic Project Disclosure</h3>
                    <div class="highlight-box">
                        <p>This platform is developed as part of the ECO5037S 2025 class project at the University of Cape Town. While we strive for best practices, users acknowledge the educational and experimental nature of this implementation.</p>
                    </div>
                </div>

                <div class="section">
                    <h2><span class="section-number">20</span> Acknowledgment</h2>
                    <div class="warning-box">
                        <p><strong>BY CLICKING "ACCEPT" WHEN PROMPTED BY THE NKADIME TELEGRAM BOT, YOU ACKNOWLEDGE THAT:</strong></p>
                        <ol>
                            <li>You have read and understood these Terms in their entirety</li>
                            <li>You agree to be bound by these Terms</li>
                            <li>You consent to the collection and use of your banking data as described</li>
                            <li>You understand the risks associated with peer-to-peer lending and blockchain technology</li>
                            <li>You meet all eligibility requirements</li>
                            <li>You will comply with all applicable laws</li>
                            <li>You understand this is an experimental, proof-of-concept platform</li>
                        </ol>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """
    return HttpResponse(html)
