# Web3 Integration for FTC LendX

Complete Python Web3 integration for interacting with FTCToken, CreditTrustToken, and LoanSystemMVP smart contracts.

## 📁 Directory Structure

```
backend/onchain/
├── README.md                  # This file
├── WEB3_USAGE_GUIDE.md       # Complete usage guide with examples
├── XRPL_EVM_SETUP.md         # XRPL EVM testnet deployment guide
├── abi/                       # Contract ABIs (auto-generated)
│   ├── FTCToken.json
│   ├── CreditTrustToken.json
│   └── LoanSystemMVP.json
├── addresses.json             # Contract addresses (auto-generated)
└── examples/
    └── complete_workflow.py   # Complete lending workflow example
```

## 🚀 Quick Start

### 1. Export ABIs from Hardhat

```bash
cd hardhat-mod
node scripts/export-abis.js
```

This copies contract ABIs and addresses to this directory.

### 2. Configure Environment

Add to your `.env` file:

```env
# Web3 Configuration
WEB3_PROVIDER_URL=http://127.0.0.1:8545  # Or XRPL EVM testnet
ADMIN_ADDRESS=0xYourAdminAddress
ADMIN_PRIVATE_KEY=0xYourPrivateKey

# Contract Addresses
FTCTOKEN_ADDRESS=0xDeployedAddress
CREDITTRUST_ADDRESS=0xDeployedAddress
LOANSYSTEM_ADDRESS=0xDeployedAddress
```

### 3. Use in Python

```python
from backend.apps.tokens.services import (
    FTCTokenService,
    LoanSystemService,
    CreditTrustTokenService,
)

# Initialize services
ftc = FTCTokenService()
loan = LoanSystemService()
ctt = CreditTrustTokenService()

# Mint tokens
result = ftc.mint("0xAddress", 1000.0)
print(f"Minted! Tx: {result['tx_hash']}")

# Check balance
balance = ftc.get_balance("0xAddress")
print(f"Balance: {balance} FTCT")
```

## 📚 Documentation

### Primary Guides

1. **[WEB3_USAGE_GUIDE.md](./WEB3_USAGE_GUIDE.md)** - Complete Python usage examples
   - All contract operations
   - Event queries
   - Django integration examples
   - Error handling

2. **[XRPL_EVM_SETUP.md](./XRPL_EVM_SETUP.md)** - XRPL EVM deployment
   - Testnet configuration
   - Faucet and wallet setup
   - Deployment steps
   - Troubleshooting

3. **[examples/complete_workflow.py](./examples/complete_workflow.py)** - Runnable example
   - End-to-end lending cycle
   - Minting, deposits, loans, repayments, withdrawals

## 🔧 Available Services

### FTCTokenService

Interact with the FTCToken (ERC20) contract:

```python
ftc = FTCTokenService()

# Admin operations
ftc.mint(to_address, amount)

# User operations
ftc.transfer(from_address, to_address, amount, private_key)
ftc.approve(owner, spender, amount, private_key)

# Queries
ftc.get_balance(address)
ftc.get_allowance(owner, spender)
ftc.get_total_supply()
```

### LoanSystemService

Interact with the LoanSystemMVP contract:

```python
loan = LoanSystemService()

# Pool operations
loan.deposit_ftct(lender_address, amount, private_key)
loan.withdraw_ftct(lender_address, shares, private_key)

# Admin operations
loan_id, result = loan.create_loan(borrower, amount, apr_bps, term_days)
loan.mark_funded(loan_id)
loan.mark_disbursed_ftct(loan_id)
loan.mark_defaulted(loan_id)

# Borrower operations
loan.mark_repaid_ftct(loan_id, on_time, amount, borrower_address, private_key)

# Queries
loan.get_total_pool()
loan.get_shares_of(address)
loan.get_loan(loan_id)
loan.calculate_interest(principal, apr_bps, term_days)
```

### CreditTrustTokenService

Interact with the CreditTrustToken (reputation) contract:

```python
ctt = CreditTrustTokenService()

# Admin operations
ctt.initialize_user(user_address, initial_score)
ctt.mint(user_address, amount)  # Increase reputation
ctt.burn(user_address, amount)  # Decrease reputation

# Queries
ctt.get_balance(address)
ctt.is_initialized(address)
```

## 💡 Common Operations

### Mint and Distribute FTCT

```python
from backend.apps.tokens.services import FTCTokenService

ftc = FTCTokenService()

# Mint to multiple addresses
addresses = [
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
]

for addr in addresses:
    result = ftc.mint(addr, 1000.0)
    print(f"Minted to {addr}: {result['tx_hash']}")
```

### Lender Deposits FTCT

```python
from django.conf import settings
from backend.apps.tokens.services import FTCTokenService, LoanSystemService

ftc = FTCTokenService()
loan = LoanSystemService()

lender = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
lender_key = "0x..."
amount = 500.0

# Step 1: Approve
ftc.approve(lender, settings.LOANSYSTEM_ADDRESS, amount, lender_key)

# Step 2: Deposit
loan.deposit_ftct(lender, amount, lender_key)

# Check shares
shares = loan.get_shares_of(lender)
print(f"Lender has {shares} shares")
```

### Complete Loan Cycle

```python
from backend.apps.tokens.services import LoanSystemService

loan = LoanSystemService()

# 1. Create loan
loan_id, _ = loan.create_loan(borrower, 200.0, 1200, 30)

# 2. Fund loan
loan.mark_funded(loan_id)

# 3. Disburse to borrower
loan.mark_disbursed_ftct(loan_id)

# 4. Borrower repays (after approving tokens)
loan.mark_repaid_ftct(loan_id, True, 205.0, borrower, borrower_key)
```

## 🌐 Network Configuration

### Local Hardhat

```env
WEB3_PROVIDER_URL=http://127.0.0.1:8545
ADMIN_ADDRESS=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
ADMIN_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### XRPL EVM Testnet

```env
WEB3_PROVIDER_URL=https://rpc-evm-sidechain.xrpl.org
ADMIN_ADDRESS=0xYourWalletAddress
ADMIN_PRIVATE_KEY=0xYourPrivateKey
```

See [XRPL_EVM_SETUP.md](./XRPL_EVM_SETUP.md) for complete setup.

## 🔒 Security Best Practices

1. **Never commit private keys** to version control
2. **Use environment variables** for sensitive data
3. **Validate all addresses** before transactions
4. **Test on local/testnet** before mainnet
5. **Monitor gas prices** and set limits
6. **Log all transactions** with tx hashes
7. **Handle errors gracefully** with try-except blocks

## 🧪 Testing

### Run Complete Workflow

```bash
# Make sure Hardhat node is running
cd hardhat-mod
npx hardhat node  # In separate terminal

# Run workflow
python backend/onchain/examples/complete_workflow.py
```

### Test Individual Operations

```python
# In Django shell
python manage.py shell

from backend.apps.tokens.services import FTCTokenService

ftc = FTCTokenService()
print(f"Connected: {ftc.web3.is_connected()}")
print(f"Chain ID: {ftc.web3.eth.chain_id}")
print(f"Block: {ftc.get_block_number()}")
```

## 🐛 Troubleshooting

### Connection Failed

```python
# Check connection
from backend.apps.tokens.services import FTCTokenService
ftc = FTCTokenService()
print(ftc.web3.is_connected())  # Should be True
```

**Solutions:**
- Verify `WEB3_PROVIDER_URL` is correct
- Ensure Hardhat node is running (local dev)
- Check network connectivity (XRPL EVM)

### Contract Not Found

**Solutions:**
- Run `node scripts/export-abis.js` from hardhat-mod
- Verify contract addresses in `.env`
- Check contracts are deployed

### Insufficient Balance

**Solutions:**
- Mint more FTCT: `ftc.mint(address, amount)`
- Request testnet funds from faucet (XRPL EVM)
- Check balance: `ftc.get_balance(address)`

## 📖 Additional Resources

- **Hardhat Docs:** [GETTING_STARTED.md](../../hardhat-mod/GETTING_STARTED.md)
- **Solidity Contracts:** [hardhat-mod/contracts/](../../hardhat-mod/contracts/)
- **Web3.py Docs:** https://web3py.readthedocs.io/
- **XRPL EVM Docs:** https://xrpl.org/evm-sidechain.html

## 🎯 Next Steps

1. ✅ Export ABIs: `cd hardhat-mod && node scripts/export-abis.js`
2. ✅ Configure environment variables
3. ✅ Run example workflow: `python backend/onchain/examples/complete_workflow.py`
4. ✅ Integrate into your Django views/tasks
5. 🚀 Deploy to XRPL EVM testnet (see XRPL_EVM_SETUP.md)

## 💬 Need Help?

- Check the troubleshooting sections in the guides
- Review example code in `examples/complete_workflow.py`
- Test operations step-by-step in Django shell
- Verify configuration in `.env` and `settings/base.py`

---

**Happy coding! 🎉**

