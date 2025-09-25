## Functional Requirements

### Broad Overview

The **XRP Telegram Bot** is a custodial crypto asset manager that integrates with the Telegram messaging platform and the XRP Ledger (XRPL) TestNet. It allows users to:

- Register using their Telegram handle  
- Automatically create XRPL TestNet accounts  
- Send XRP to other bot users  
- Check XRP balances  
- Request historical price data using the CoinGecko API  

> **Note:** This system is intended for test and educational use, not for real-world XRP MainNet transactions.


### Scope

**In Scope:**

- User registration via Telegram `/start` command  
- Custodial XRPL TestNet wallet creation and key management  
- Peer-to-peer XRP transfers between users via Telegram handles  
- Balance lookups on XRPL TestNet  
- Historical XRP price queries using date ranges  
- Multi-currency support for price data (USD, ZAR)  
- Webhook-based integration with the Telegram Bot API  

**Out of Scope:**

- XRPL MainNet deployment  
- Fiat on/off ramps (e.g., card payments, withdrawals)  
- Multi-signature wallet support  
- Portfolio tracking or trading features  
- Integration with other blockchain networks  

---

### Requirements

#### Telegram Bot Interface

- **FR-1: User Registration on `/start`**  
  Register users with their Telegram handle and create a new XRPL TestNet wallet.  
  The bot will respond with a welcome message and the new XRPL address.  
  **Requirement:** Must complete within 10 seconds.

- **FR-2: List Commands with `/help`**  
  The bot must list all supported commands with brief descriptions and usage examples.  
  Commands should be grouped by category (Account, Payments, Prices, General).

- **FR-3: Balance Inquiry with `/balance`**  
  The bot must return the current XRP balance in real-time from the XRPL TestNet.  
  Optionally, it should display equivalent values in USD or ZAR and support other XRPL-issued tokens.

- **FR-4: XRP Transfers with `/send`**  
  Users can send XRP by specifying a Telegram handle and amount.  
  The bot must validate the recipient, confirm the sender’s balance, prompt for confirmation,  
  and notify both parties of the transaction outcome and fee.

- **FR-5: Historical Price Queries with `/price`**  
  The bot must support date-range queries for historical XRP price data.  
  It should validate start and end dates, limit queries to max 5 years,  
  support relative dates like “last 7 days” or “last month,”  
  and return readable price data with summary statistics.  
  Supported currencies: **USD** (default) and **ZAR**.

- **FR-6: Error Handling**  
  Provide friendly error messages for malformed commands, handle network/API failures gracefully,  
  and communicate rate limiting to users.

- **FR-7: Standard Telegram Commands**  
  Support `/start`, `/help`, `/settings`, and `/cancel`.  
  All commands must be case-insensitive and support auto-complete.

#### XRPL Account Management

- **FR-8: Wallet Generation**  
  Generate XRPL TestNet wallets using `xrpl-py` SDK.  
  Encrypt secrets with Fernet and store securely in DB.  
  **Requirement:** Must complete within 5 seconds.

- **FR-9: Initial Funding**  
  Each new account must receive ≥100 XRP from the TestNet faucet.  
  Trigger up to 3 retries if funding fails and notify users after confirmation.

- **FR-10: Secure Key Management**  
  Store private keys encrypted at rest (Fernet).  
  Keep encryption keys separate from main DB, never log/expose keys,  
  and only decrypt keys for transaction signing.

- **FR-11: Balance Monitoring**  
  Retrieve up-to-date balances on request, cache temporarily,  
  and track balance changes after transactions.

- **FR-12: Transaction Execution**  
  Sign transactions securely, validate balances/addresses,  
  calculate/display fees, and confirm success/failure to sender and recipient.  
  Implement atomic processing with rollback if needed.

#### Historical Price Data

- **FR-13: CoinGecko Integration**  
  Use CoinGecko’s Market Chart Range API.  
  Convert input dates to UNIX timestamps, handle rate limits/timeouts/failures,  
  and cache frequent queries.

- **FR-14: Date Validation**  
  Accept ISO (YYYY-MM-DD) and relative date terms.  
  Ensure start < end date and max range ≤ 5 years.

- **FR-15: Data Presentation**  
  Show daily closing prices, summarize with min/max/avg,  
  and display in user’s preferred currency.


### Non-Functional Requirements

- **Security:**  
  - Fernet encryption for keys  
  - No sensitive info in logs  
  - HTTPS for all communications  
  - Prevent injection attacks  

- **Performance:**  
  - Response time ≤ 2s under normal load  
  - Indexed queries, caching for price/balance lookups  

- **Reliability:**  
  - 99% uptime during business hours  
  - Retry mechanisms for failed operations  
  - Atomic, consistent transactions  

- **Testability:**  
  - Unit tests for core logic  
  - Integration tests for XRPL and CoinGecko  
  - Mockable APIs, separate test/production DBs  

- **Deployability:**  
  - Packaged with Docker, `.env`-based config  
  - Automated migrations  
  - Zero-downtime deploys and documented rollback
  - Deploy to Render.com or similar platform


### Future Enhancements

- **Functional Additions:**  
  Support XRPL token balances, price alert subscriptions,  
  user-facing portfolio dashboard, multi-signature wallets.

- **Admin & Monitoring Tools:**  
  Web dashboard for admin and transaction monitoring.

- **Scalability:**  
  Transition toward microservices, event-driven queues,  
  database sharding, and optional CDN for global performance.

