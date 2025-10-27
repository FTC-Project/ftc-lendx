# LoanSystemMVP Contract Documentation

## Overview

This project implements a minimal viable product (MVP) for a decentralized lending system. The system consists of three main contracts:

1. **FTCToken** – ERC20 token representing fungible assets in the lending ecosystem.

2. **CreditTrustToken** (CTT) – Soulbound reputation token tracking borrower trust scores.

3. **LoanSystemMVP** – Main lending contract combining loan management, escrow, and liquidity pooling.

The system allows lenders to deposit ERC20 tokens (FTCT), enables admin-managed loan creation and disbursement, and tracks borrower reputation via CTT.

## Contracts

### 1. FTCToken

**Purpose:**  
FTCToken is a standard ERC20 token used in the ecosystem for lending and borrowing. It represents fungible assets deposited into the loan pool.  

**Key Features:**
- ERC20 token with `mint` capability.
- Only the owner (admin) can mint new tokens.
- Can be used to deposit into the lending pool instead.

**Constructor:**  
```solidity
constructor(address admin)
```

**Function:** 
```solidity
mint(address to, uint256 amount) // Mints new FTCT tokens to the specified address (admin only)
```
***
### 2. CreditTrustToken

**Purpose:**

CTT is a soulbound token used to track borrower reputation. Balances are non-transferable, can be negative, and are modified only by the admin or the `LoanSystemMVP` contract.



**Key Features**
- Tracks an `int256` balance for each user (`tokenBalance`) representing trust score.
- Users must be initialized before interacting with loans.
- Reputation is minted for on-time repayment and burned on default.
- Only admin or `LoanSystemMVP` contract can modify balances.
- No ERC20 transfer functionality — soulbound by design.


**State Variables**
| Variable        | Description                                                  |
|----------------|--------------------------------------------------------------|
| `tokenBalance` | Borrower trust scores (`int256`)                              |
| `isInitialized`| Tracks whether a borrower is initialized                      |
| `admin`        | Admin address                                                 |
| `loanSystem`   | Trusted `LoanSystemMVP` contract allowed to mint/burn tokens |

---

**Functions**
- `setLoanSystem(address _loanSystem)` – Authorizes the `LoanSystemMVP` contract.
- `initializeUser(address user, uint256 initialTrustScore)` – Initializes a user with a trust score.
- `mint(address user, uint256 amount)` – Increases user trust score.
- `burn(address user, uint256 amount)` – Decreases user trust score.
- `setAdmin(address newAdmin)` – Rotates admin.

***
### 3. LoanSystemMVP

### Purpose
This contract is the core of the lending platform, combining a liquidity pool, escrow management, and loan lifecycle management. It integrates both `FTCToken` (for deposits) and `CreditTrustToken` (CTT) for borrower reputation.

---

### Key Features
- Lenders can deposit FTCT tokens to the pool and receive shares proportional to their contribution.
- Admin can create loans, fund them from the pool, disburse to borrowers, and mark repayment or default.
- Borrowers’ trust scores in CTT are updated automatically upon repayment or default.
- Supports simple interest loans calculated using:  
  `principal * APR * term / 36500`

---

### State Variables
| Variable      | Description                                                  |
|---------------|--------------------------------------------------------------|
| `totalPool`   | Total liquidity (ETH/FTCT) including interest                |
| `totalShares` | Total shares issued to lenders                               |
| `sharesOf`    | Mapping of lender address → share balance                    |
| `FTCToken`    | Reference to `FTCToken` contract                             |
| `ctt`         | Reference to `CreditTrustToken` contract                     |
| `loans`       | Mapping of loan IDs → `Loan` struct                          |
| `nextId`      | Counter for loan IDs                                         |

---

## 🔗 How the Contracts Interact


### FTCToken ↔ LoanSystemMVP
- Lenders deposit FTCT tokens into the LoanSystem pool via `depositFTCT`.
- Loans can be disbursed in FTCT tokens via `markDisbursedFTCT`.
- Borrowers repay in FTCT tokens via `markRepaidFTCT`.

---

### CreditTrustToken ↔ LoanSystemMVP
- LoanSystem initializes borrower in CTT when creating a loan.
- On loan repayment, LoanSystem mints trust to borrower.
- On default, LoanSystem burns trust from borrower.

---

### Admin
- The admin account has full control over loan management and token operations.
- Admin can rotate themselves, authorize LoanSystem in CTT, and mint FTCT tokens.

---

### 🧾 Summary
| Contract         | Role                                                                 |
|------------------|----------------------------------------------------------------------|
| `FTCToken`       | Fungible token for deposits and lending                              |
| `CreditTrustToken (CTT)` | Soulbound token for borrower reputation, only modified by LoanSystem/admin |
| `LoanSystemMVP`  | Core contract managing liquidity, loans, escrow, repayment, defaults, and reputation updates |

Together, these contracts implement a decentralized lending platform with pooled liquidity, interest accrual, and reputation-based borrower incentives.
