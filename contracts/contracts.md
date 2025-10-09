# Concept
My idea is for there to be 4 main contracts, 1 for handling loans, 1 for handling the liquidity pooling, 1 for escrow and 1 for releasing creditTrustTokens.

There are **four main contracts**:

1. **LoanRegistry** – orchestrates and records all loan activity.  
2. **LiquidityPool** – manages pooled lender funds.  
3. **EscrowContract** – temporarily holds funds during loan and repayment flows.  
4. **CreditTrustToken** – issues non-transferable "credit trust" tokens to reward reliable borrowers.

# P2P Loan Sequence Diagram

```{mermaid}
sequenceDiagram
    participant Borrower
    participant LoanRegistry
    participant Escrow
    participant Lender
    participant CreditToken

    Borrower->>LoanRegistry: requestLoan(amount, duration)
    LoanRegistry->>Escrow: createEscrow(borrower, amount)
    Lender->>LoanRegistry: fundLoan(loanId, amount)
    LoanRegistry->>Escrow: depositFunds(lender, amount)
    Escrow-->>Borrower: releaseFunds()

    Borrower->>Escrow: repayLoan(amount)
    Escrow->>LoanRegistry: markRepaid(loanId)
    LoanRegistry->>CreditToken: mintCreditToken(borrower, repaymentScore)
    CreditToken-->>Borrower: issueCreditToken()
```

# LiquidityPool Loan Sequence Diagram

```{mermaid}
sequenceDiagram
    participant Borrower
    participant LoanRegistry
    participant Escrow
    participant LiquidityPool
    participant CreditToken
    participant Lender

    Lender->>LiquidityPool: depositLiquidity(amount)
    LiquidityPool-->>LoanRegistry: updatePoolBalance()

    Borrower->>LoanRegistry: requestLoan(amount, duration)
    LoanRegistry->>LiquidityPool: allocateFunds(loanId, amount)
    LiquidityPool->>Escrow: depositFunds(amount)
    Escrow-->>Borrower: releaseFunds()

    Borrower->>Escrow: repayLoan(amount)
    Escrow->>LiquidityPool: returnFundsWithInterest(amount)
    LiquidityPool->>LoanRegistry: markRepaid(loanId)
    LoanRegistry->>CreditToken: mintCreditToken(borrower, repaymentScore)
    CreditToken-->>Borrower: issueCreditToken()
```


# 1. LoanRegistry Contract (Core Logic)

**Purpose:**  
Acts as the main controller and single source of truth for all loans on the platform.

**Responsibilities:**
- Registers all loans (whether P2P or from the pool).
- Keeps mappings like `loanId → borrower → lender(s) → status`.
- Handles loan lifecycle states: `Requested → Funded → Active → Repaid → Defaulted`.
- Calls functions from other contracts to issue, escrow, and close loans.

**Interactions:**
- Calls `EscrowContract` to lock/release funds.
- Calls `CreditTokenContract` to mint reputation tokens after repayment.
- Interfaces with `LiquidityPool` if the loan is P2Pool instead of P2P.

---

# 2. LiquidityPool Contract

**Purpose:**  
Enables tech-savvy lenders to deposit funds collectively, which are used to fulfill borrower requests when no direct P2P lender is matched.

**Responsibilities:**
- Accepts deposits from lenders → tracks share balances.
- Provides funds to `LoanRegistry` on borrower requests.
- Receives repayments and updates lenders’ share values.
- Can implement a basic yield distribution mechanism (e.g., proportional to pool share).

**Interactions:**
- Invoked by `LoanRegistry` when a borrower opts for pooled lending.
- Sends loan funds to `EscrowContract`.
- Receives repayments (via `LoanRegistry` or directly from `EscrowContract`).

---

# 3. EscrowContract

**Purpose:**  
Handles temporary custody of funds during loan creation and repayment — ensures trustless transfers.

**Responsibilities:**
- Holds lender or pool funds until the loan is activated.
- Releases funds to borrower once `LoanRegistry` marks it “Approved”.
- Locks repayments until verified, then distributes to lender(s) or pool.

**Interactions:**
- Controlled by `LoanRegistry` (never directly by users).
- Receives funds from `LiquidityPool` or individual lender.
- Sends funds to borrower and back to lender(s) after repayment.

---

# 4. CreditTrustToken Contract

**Purpose:**  
Rewards borrowers who repay on time with a non-transferable credit reputation token (soulbound token).

**Responsibilities:**
- Mint new tokens when `LoanRegistry` marks a loan as “Repaid”.
- In future, store credit metadata (e.g., number of successful repayments).
- Tokens can be queried by the scoring engine or Telegram bot to assess reliability.

**Interactions:**
- Called by `LoanRegistry` upon successful repayment.
- Read by the off-chain Python credit scoring engine to feed future scoring logic.

---

# Workflow

**P2P Loan**
1. Borrower submits loan request → LoanRegistry creates record.
2. Lender accepts → funds sent to EscrowContract.
3. LoanRegistry approves → Escrow releases funds to borrower.
4. Borrower repays → Escrow returns funds + interest to lender.
5. LoanRegistry calls CreditTrustToken to mint a token for borrower.

**Pool-based Loan**
1. Borrower submits loan request → chooses “Pool”.
2. LoanRegistry requests funding from LiquidityPool.
3. Pool transfers funds to EscrowContract.
4. Borrower receives funds → later repays → Escrow returns repayment to pool.
5. Pool updates internal balances for all liquidity providers.
6. LoanRegistry mints a CreditTrustToken for borrower.