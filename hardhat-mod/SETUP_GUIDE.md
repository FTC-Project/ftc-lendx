# Complete Setup Guide: Minting and Funding the LoanSystemMVP

This guide walks you through setting up Hardhat, minting FTCTokens, and funding the LoanSystemMVP contract.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Starting Hardhat Network](#starting-hardhat-network)
4. [Deploying Contracts](#deploying-contracts)
5. [Minting FTCTokens](#minting-ftctokens)
6. [Funding the LoanSystem](#funding-the-loansystem)
7. [Complete Workflow Example](#complete-workflow-example)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Node.js (v18 or higher)
- npm or yarn
- Two terminal windows

---

## Initial Setup

### Step 1: Install Dependencies

```bash
cd hardhat-mod
npm install
```

### Step 2: Create Environment File

Copy the example environment file and use it as your `.env.hardhat`:

```bash
cp .env.hardhat.example .env.hardhat
```

The `.env.hardhat` file contains:
- **RPC_URL**: Local Hardhat node URL (default: http://127.0.0.1:8545)
- **Contract Addresses**: CTT, FTCT, and LoanSystem addresses
- **Admin Keys**: Private and public keys for the admin wallet
- **Test Account Keys**: Additional accounts for lenders and borrowers

---

## Starting Hardhat Network

### Terminal 1: Start the Hardhat Node

```bash
cd hardhat-mod
npx hardhat node
```

This will:
- Start a local Ethereum network on `http://127.0.0.1:8545`
- Create 20 test accounts with 10,000 ETH each
- Display the private keys for these accounts
- Keep running in the foreground

**Keep this terminal open!** The node must stay running for all subsequent commands.

---

## Deploying Contracts

### Terminal 2: Deploy the Contracts

If contracts aren't already deployed, run:

```bash
cd hardhat-mod
npx hardhat ignition deploy ignition/modules/LoanSystemFullModule.ts --network localhost
```

This deploys:
1. **CreditTrustToken** (CTT) - Soulbound reputation token
2. **FTCToken** (FTCT) - ERC20 fungible token for lending
3. **LoanSystemMVP** - Main lending protocol

After deployment, update the contract addresses in `.env.hardhat` with the values from `ignition/deployments/chain-31337/deployed_addresses.json`.

---

## Understanding the System

### Contract Roles

1. **Admin Wallet**: 
   - Can mint FTCTokens
   - Can create, fund, and disburse loans
   - Can mark loans as defaulted

2. **Lender Wallet**:
   - Deposits FTCTokens into the pool
   - Receives pool shares representing their stake
   - Earns interest when borrowers repay

3. **Borrower Wallet**:
   - Receives loans disbursed by admin
   - Repays loans with principal + interest
   - Earns/loses CreditTrust tokens based on repayment behavior

---

## Minting FTCTokens

The admin wallet (account #0) is the owner of the FTCToken contract and can mint new tokens.

### Check Current Token Owner

```bash
node scripts/cli.js token-admin $ADMIN_PRIVATE_KEY
```

### Mint Tokens to a Wallet

**Syntax:**
```bash
node scripts/cli.js mint-token <recipientAddress> <amount> <adminPrivateKey>
```

**Example: Mint 10,000 FTCT to Admin**
```bash
node scripts/cli.js mint-token 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 10000 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

**Example: Mint 5,000 FTCT to Lender #1**
```bash
node scripts/cli.js mint-token 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 5000 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### Check Token Balance

```bash
node scripts/cli.js token-balance 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

---

## Funding the LoanSystem

To fund the LoanSystem pool, lenders deposit FTCTokens and receive pool shares.

### Step 1: Approve LoanSystem to Spend Tokens

This is handled automatically by the `deposit-ftct-all` command.

### Step 2: Deposit Tokens into the Pool

**Syntax:**
```bash
node scripts/cli.js deposit-ftct-all <amount> <lenderPrivateKey>
```

**Example: Deposit 1,000 FTCT from Lender #1**
```bash
node scripts/cli.js deposit-ftct-all 1000 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
```

This command:
1. Approves the LoanSystem to spend tokens
2. Calls `depositFTCT()` on the LoanSystem
3. Mints pool shares to the lender

### Check Pool Status

**Check Total Pool Balance:**
```bash
node scripts/cli.js pool 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

**Check Lender's Shares:**
```bash
node scripts/cli.js shares 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

---

## Complete Workflow Example

Here's a complete end-to-end example of the lending flow:

### 1. Setup and Mint Initial Tokens

```bash
# Mint 10,000 FTCT to Admin
node scripts/cli.js mint-token 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 10000 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# Mint 5,000 FTCT to Lender #1
node scripts/cli.js mint-token 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 5000 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# Mint 1,000 FTCT to Borrower #1 (for repayment)
node scripts/cli.js mint-token 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC 1000 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### 2. Fund the Pool (Lender Deposits)

```bash
# Lender #1 deposits 2,000 FTCT
node scripts/cli.js deposit-ftct-all 2000 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d

# Check pool balance
node scripts/cli.js pool 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### 3. Create a Loan (Admin)

```bash
# Create loan: 500 FTCT, 12% APR (1200 bps), 30 days
node scripts/cli.js create-loan 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC 500 1200 30 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# This will output a loan ID (e.g., Loan ID: 1)
```

### 4. Fund the Loan (Admin)

```bash
# Mark loan as funded (reserves pool funds)
node scripts/cli.js fund-loan 1 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### 5. Disburse the Loan (Admin)

```bash
# Disburse FTCT to borrower
node scripts/cli.js disburse-loan-ftct 1 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# Check borrower's balance (should have received 500 FTCT)
node scripts/cli.js token-balance 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### 6. Repay the Loan (Borrower)

```bash
# Calculate repayment: 500 principal + interest
# Interest = 500 * 1200 * 30 / (10000 * 365) ≈ 4.93 FTCT
# Total = ~504.93 FTCT (use 505 to be safe)

# Borrower repays loan
node scripts/cli.js repay-ftct-all 1 true 505 0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a

# Check borrower's trust score (should increase)
node scripts/cli.js trust 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### 7. Withdraw from Pool (Lender)

```bash
# Check lender's shares
node scripts/cli.js shares 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# Withdraw (e.g., 1000 shares)
node scripts/cli.js withdrawFTCT 1000 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d

# Check final balance (should include earned interest)
node scripts/cli.js token-balance 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

---

## Quick Reference Commands

### Token Management
```bash
# Mint tokens to an address
node scripts/cli.js mint-token <address> <amount> <adminPrivateKey>

# Check token balance
node scripts/cli.js token-balance <address> <anyPrivateKey>

# Check token owner
node scripts/cli.js token-admin <anyPrivateKey>
```

### Pool Operations
```bash
# Deposit FTCT into pool
node scripts/cli.js deposit-ftct-all <amount> <lenderPrivateKey>

# Withdraw FTCT from pool
node scripts/cli.js withdrawFTCT <shareAmount> <lenderPrivateKey>

# Check pool total
node scripts/cli.js pool <anyPrivateKey>

# Check user shares
node scripts/cli.js shares <userAddress> <anyPrivateKey>
```

### Loan Management
```bash
# Create loan
node scripts/cli.js create-loan <borrowerAddress> <amount> <aprBps> <termDays> <adminPrivateKey>

# Fund loan
node scripts/cli.js fund-loan <loanId> <adminPrivateKey>

# Disburse loan (FTCT)
node scripts/cli.js disburse-loan-ftct <loanId> <adminPrivateKey>

# Repay loan (FTCT)
node scripts/cli.js repay-ftct-all <loanId> <onTime> <amount> <borrowerPrivateKey>

# Default loan
node scripts/cli.js default-loan <loanId> <adminPrivateKey>

# List all loans
node scripts/cli.js get-loans
```

### Reputation
```bash
# Check trust score
node scripts/cli.js trust <userAddress> <anyPrivateKey>

# Check all admins
node scripts/cli.js check-admins <anyPrivateKey>
```

---

## Troubleshooting

### Contract Not Deployed
**Error**: "Error: could not decode result data"

**Solution**: Make sure contracts are deployed:
```bash
npx hardhat ignition deploy ignition/modules/LoanSystemFullModule.ts --network localhost
```

### Insufficient Balance
**Error**: "Insufficient balance" or "Transfer amount exceeds balance"

**Solution**: Mint more tokens to the wallet:
```bash
node scripts/cli.js mint-token <address> <amount> <adminPrivateKey>
```

### Transfer Failed
**Error**: "FTCT transfer failed" or "ERC20: insufficient allowance"

**Solution**: Use the `*-all` commands which handle approval automatically:
- `deposit-ftct-all` (instead of manual approve + deposit)
- `repay-ftct-all` (instead of manual approve + repay)

### Network Not Running
**Error**: "connect ECONNREFUSED 127.0.0.1:8545"

**Solution**: Start the Hardhat node in a separate terminal:
```bash
npx hardhat node
```

### Wrong Network
**Error**: Contract addresses don't match

**Solution**: Make sure you're using the correct network and update `.env.hardhat` with the deployed addresses from:
```
ignition/deployments/chain-31337/deployed_addresses.json
```

---

## Understanding the Flow

### Token Flow (FTCT):
1. **Admin mints** FTCT tokens to various addresses
2. **Lenders deposit** FTCT into the LoanSystem pool
3. **LoanSystem holds** FTCT in the pool
4. **Admin creates and funds** loans from the pool
5. **Admin disburses** FTCT to borrowers
6. **Borrowers repay** FTCT (principal + interest) to the pool
7. **Lenders withdraw** FTCT (with earned interest) from the pool

### Reputation Flow (CTT):
1. **LoanSystem initializes** borrower's CTT score at 0 on first loan
2. **On-time repayment**: Borrower earns CTT (mint amount = principal)
3. **Late repayment**: Borrower earns half CTT (mint amount = principal / 2)
4. **Default**: Borrower loses CTT (burn amount = principal)
5. **CTT tokens are soulbound** (cannot be transferred)

---

## Next Steps

After setting up the basic flow, you can:
1. Create multiple loans with different terms
2. Test default scenarios
3. Monitor how pool shares appreciate with interest
4. Track borrower reputation over multiple loans
5. Integrate with your Python backend using Web3.py

For Python/Web3 integration, see the backend integration guide in the main project README.

