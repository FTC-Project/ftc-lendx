# 🚀 Quick Start: Minting & Funding LoanSystemMVP

This is the fastest way to get your loan system up and running with minted FTCTokens.

## ⚡ Super Quick Setup (5 minutes)

### 1️⃣ Create Environment File

```bash
cd hardhat-mod
cp .env.hardhat.example .env.hardhat
```

The file is already configured with the correct contract addresses and test account keys!

### 2️⃣ Install Dependencies (if not done)

```bash
npm install
```

### 3️⃣ Start Hardhat Network

**Open a new terminal window** and run:

```bash
cd hardhat-mod
npx hardhat node
```

Keep this running! Don't close this terminal.

### 4️⃣ Run Auto-Setup Script

**In your original terminal**, run:

```bash
node scripts/quick-setup.js
```

This script will automatically:
- ✅ Mint 10,000 FTCT to the Admin
- ✅ Mint 5,000 FTCT to Lender #1
- ✅ Mint 2,000 FTCT to Borrower #1
- ✅ Deposit 2,000 FTCT from Lender #1 into the pool

**That's it!** Your system is now funded and ready.

---

## 🎯 What Just Happened?

### The Setup Created:

| Account | Role | FTCT Balance | Pool Shares |
|---------|------|--------------|-------------|
| 0xf39F...2266 | Admin | 10,000 | 0 |
| 0x7099...79C8 | Lender #1 | 3,000 | 2,000 |
| 0x3C44...93BC | Borrower #1 | 2,000 | 0 |

**Pool Total:** 2,000 FTCT (available for loans)

---

## 🏃 Next Steps: Create Your First Loan

### Step 1: Create a Loan

```bash
node scripts/cli.js create-loan 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC 500 1200 30 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

This creates a loan for:
- **Borrower:** 0x3C44...93BC (Borrower #1)
- **Amount:** 500 FTCT
- **APR:** 12% (1200 basis points)
- **Term:** 30 days

**Output:** `Loan created with ID: 1`

### Step 2: Fund the Loan

```bash
node scripts/cli.js fund-loan 1 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

This reserves 500 FTCT from the pool for loan #1.

### Step 3: Disburse to Borrower

```bash
node scripts/cli.js disburse-loan-ftct 1 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

This sends 500 FTCT to the borrower's wallet.

### Step 4: Borrower Repays

```bash
# Calculate interest: 500 * 12% * 30/365 ≈ 4.93 FTCT
# Total repayment: 500 + 4.93 ≈ 505 FTCT

node scripts/cli.js repay-ftct-all 1 true 505 0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
```

The borrower repays 505 FTCT (principal + interest) and earns reputation points!

---

## 📋 Essential Commands

### Check Balances

```bash
# Check FTCT balance
node scripts/cli.js token-balance 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# Check pool total
node scripts/cli.js pool 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# Check pool shares
node scripts/cli.js shares 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# Check trust score
node scripts/cli.js trust 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### List All Loans

```bash
node scripts/cli.js get-loans
```

### Mint More Tokens

```bash
node scripts/cli.js mint-token <address> <amount> 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

---

## 🔑 Account Reference

Save these for easy copy-paste:

### Admin (Account #0)
```
Address: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Private Key: 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### Lender #1 (Account #1)
```
Address: 0x70997970C51812dc3A010C7d01b50e0d17dc79C8
Private Key: 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
```

### Borrower #1 (Account #2)
```
Address: 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
Private Key: 0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
```

---

## 🐛 Troubleshooting

### "ECONNREFUSED 127.0.0.1:8545"
➡️ Start the Hardhat node: `npx hardhat node`

### "Insufficient balance"
➡️ Mint more tokens: `node scripts/quick-setup.js`

### "FTCT transfer failed"
➡️ Use the `-all` commands (they handle approvals automatically):
- `deposit-ftct-all`
- `repay-ftct-all`

### Contracts not found
➡️ Redeploy contracts:
```bash
npx hardhat ignition deploy ignition/modules/LoanSystemFullModule.ts --network localhost
```

---

## 📚 Want More Details?

See the complete guide: **[SETUP_GUIDE.md](./SETUP_GUIDE.md)**

---

## 🎉 You're Ready!

Your loan system is now fully funded and operational. You can:
- ✅ Create loans with any terms
- ✅ Disburse funds to borrowers
- ✅ Track repayments and defaults
- ✅ Monitor reputation scores
- ✅ Calculate lender returns

Happy lending! 🚀

