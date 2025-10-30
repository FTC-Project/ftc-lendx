# XRPL EVM Testnet Setup Guide

Complete guide for deploying and using your contracts on the XRPL EVM Testnet.

## Overview

XRPL EVM Sidechain is an Ethereum-compatible blockchain that connects to the XRP Ledger. It allows you to deploy Solidity smart contracts while leveraging XRPL's features.

## Prerequisites

- MetaMask or similar Web3 wallet
- Node.js and npm
- Python 3.11+
- Hardhat project setup

---

## Step 1: Get XRPL EVM Testnet Funds

### 1.1 Configure MetaMask for XRPL EVM Testnet

Add XRPL EVM Devnet to MetaMask:

**Network Details:**
- **Network Name:** XRPL EVM Devnet
- **RPC URL:** `https://rpc-evm-sidechain.xrpl.org`
- **Chain ID:** `1440002` (or check current docs)
- **Currency Symbol:** XRP
- **Block Explorer:** `https://evm-sidechain.xrpl.org`

### 1.2 Request Testnet Funds

1. Visit: [https://faucet.devnet.xrpl.org/](https://faucet.devnet.xrpl.org/)
2. Enter your wallet address
3. Request testnet XRP
4. Wait for confirmation (usually instant)

**Recommended:** Request at least 100 XRP for testing and gas fees.

---

## Step 2: Configure Hardhat for XRPL EVM

### 2.1 Update hardhat.config.ts

Your `hardhat-mod/hardhat.config.ts` should include:

```typescript
import type { HardhatUserConfig } from "hardhat/config";
import * as dotenv from "dotenv";

dotenv.config({ path: ".env.hardhat" });

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.28",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },
  networks: {
    xrpl_evm_devnet: {
      url: process.env.XRPL_RPC_URL || "https://rpc-evm-sidechain.xrpl.org",
      accounts: [process.env.ADMIN_PRIVATE_KEY!],
      chainId: 1440002,
    },
    localhost: {
      url: "http://127.0.0.1:8545",
      accounts: [process.env.ADMIN_PRIVATE_KEY!],
    },
  },
};

export default config;
```

### 2.2 Create .env.hardhat for XRPL EVM

```env
# XRPL EVM Devnet Configuration
XRPL_RPC_URL=https://rpc-evm-sidechain.xrpl.org

# Your wallet (NOT hardhat test account!)
ADMIN_PRIVATE_KEY=0xYourPrivateKeyHere
ADMIN_PUBLIC_KEY=0xYourWalletAddressHere

# These will be populated after deployment
FTCTOKEN_ADDRESS=
CREDITTRUST_ADDRESS=
LOANSYSTEM_ADDRESS=
```

⚠️ **Security Warning:** Never commit real private keys to git!

---

## Step 3: Deploy Contracts to XRPL EVM

### 3.1 Compile Contracts

```bash
cd hardhat-mod
npx hardhat compile
```

### 3.2 Deploy to XRPL EVM Devnet

```bash
npx hardhat ignition deploy ignition/modules/LoanSystemFullModule.ts --network xrpl_evm_devnet
```

**Expected output:**
```
✔ Confirm deploy to network xrpl_evm_devnet (1440002)? … yes
...
✅ CreditTrustToken deployed to: 0x...
✅ FTCToken deployed to: 0x...
✅ LoanSystemMVP deployed to: 0x...
```

### 3.3 Save Deployment Addresses

Copy the deployed addresses and update your `.env.hardhat`:

```env
FTCTOKEN_ADDRESS=0xDeployedFTCTokenAddress
CREDITTRUST_ADDRESS=0xDeployedCreditTrustAddress
LOANSYSTEM_ADDRESS=0xDeployedLoanSystemAddress
```

---

## Step 4: Verify Deployment

### 4.1 Check Contracts on Explorer

Visit: `https://evm-sidechain.xrpl.org/address/YOUR_CONTRACT_ADDRESS`

You should see:
- Contract creation transaction
- Contract code
- Transaction history

### 4.2 Test with Hardhat Console

```bash
npx hardhat console --network xrpl_evm_devnet
```

In the console:

```javascript
const FTCToken = await ethers.getContractFactory("FTCToken");
const ftc = FTCToken.attach("YOUR_FTCTOKEN_ADDRESS");
const balance = await ftc.balanceOf("YOUR_ADDRESS");
console.log("Balance:", ethers.formatEther(balance));
```

---

## Step 5: Configure Python Backend

### 5.1 Update Django .env

Create or update `.env` in your project root:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/ftc_lendx

# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# XRPL EVM Configuration
WEB3_PROVIDER_URL=https://rpc-evm-sidechain.xrpl.org

# Admin Wallet
ADMIN_ADDRESS=0xYourWalletAddress
ADMIN_PRIVATE_KEY=0xYourPrivateKey

# Contract Addresses (from deployment)
FTCTOKEN_ADDRESS=0xDeployedFTCTokenAddress
CREDITTRUST_ADDRESS=0xDeployedCreditTrustAddress
LOANSYSTEM_ADDRESS=0xDeployedLoanSystemAddress
```

### 5.2 Export ABIs to Backend

```bash
cd hardhat-mod
node scripts/export-abis.js
```

This copies ABIs to `backend/onchain/abi/` and addresses to `backend/onchain/addresses.json`.

---

## Step 6: Test Python Integration

### 6.1 Test Connection

```python
from backend.apps.tokens.services import FTCTokenService

ftc = FTCTokenService()
print(f"Connected to: {ftc.web3.provider.endpoint_uri}")
print(f"Chain ID: {ftc.web3.eth.chain_id}")
print(f"Block: {ftc.get_block_number()}")
```

**Expected output:**
```
Connected to: https://rpc-evm-sidechain.xrpl.org
Chain ID: 1440002
Block: 123456
```

### 6.2 Check Contract Owner

```python
owner = ftc.get_owner()
print(f"FTCToken owner: {owner}")
print(f"Your address: {settings.ADMIN_ADDRESS}")
assert owner.lower() == settings.ADMIN_ADDRESS.lower()
```

### 6.3 Mint Test Tokens

```python
# Mint 1000 FTCT to yourself
result = ftc.mint(
    to_address=settings.ADMIN_ADDRESS,
    amount=1000.0,
)

print(f"Minted! Tx: {result['tx_hash']}")
print(f"View on explorer: https://evm-sidechain.xrpl.org/tx/{result['tx_hash']}")

# Check balance
balance = ftc.get_balance(settings.ADMIN_ADDRESS)
print(f"Balance: {balance} FTCT")
```

---

## Step 7: Run Complete Workflow

### 7.1 Update Workflow Script

Edit `backend/onchain/examples/complete_workflow.py` to use your wallet addresses instead of Hardhat test accounts.

### 7.2 Run Workflow

```bash
python backend/onchain/examples/complete_workflow.py
```

This will:
1. ✅ Mint FTCT to lender and borrower
2. ✅ Lender deposits into pool
3. ✅ Create and disburse loan
4. ✅ Borrower repays loan
5. ✅ Lender withdraws with interest

---

## Troubleshooting

### Connection Issues

**Error:** `Failed to connect to Web3 provider`

**Solutions:**
- Check internet connection
- Verify RPC URL is correct: `https://rpc-evm-sidechain.xrpl.org`
- Try alternative RPC: Check XRPL docs for backup endpoints

### Insufficient Funds

**Error:** `insufficient funds for gas * price + value`

**Solutions:**
- Request more testnet XRP from faucet
- Check balance: `ftc.web3.eth.get_balance(YOUR_ADDRESS)`
- Wait for pending transactions to complete

### Wrong Network

**Error:** `Transaction has incorrect chain ID`

**Solutions:**
- Verify `WEB3_PROVIDER_URL` matches deployment network
- Check `chainId` in hardhat.config.ts matches XRPL EVM
- Redeploy contracts if needed

### Contract Not Found

**Error:** `Could not decode contract function call`

**Solutions:**
- Verify contract addresses are correct
- Run `node scripts/export-abis.js` again
- Check contracts are deployed: Visit block explorer

### Nonce Issues

**Error:** `nonce too low` or `already known`

**Solutions:**
- Wait for pending transactions to confirm
- Check transaction status on block explorer
- Clear pending transactions in MetaMask if needed

---

## Gas Optimization

XRPL EVM gas costs are typically low, but here are tips for optimization:

1. **Batch operations** when possible
2. **Use appropriate gas limits** (don't over-estimate)
3. **Monitor gas prices** (usually stable on testnet)
4. **Optimize contract calls** (use read functions when possible)

### Check Gas Usage

```python
from backend.apps.tokens.services import FTCTokenService

ftc = FTCTokenService()

# Mint tokens and check gas used
result = ftc.mint("0xAddress", 100.0)
print(f"Gas used: {result['gas_used']}")
print(f"Gas price: {ftc.web3.eth.gas_price}")
```

---

## Production Deployment (Mainnet)

⚠️ **IMPORTANT:** Testnet is for development only!

When ready for mainnet:

1. **Audit contracts** thoroughly
2. **Test extensively** on testnet
3. **Use hardware wallet** for mainnet admin keys
4. **Set up monitoring** and alerts
5. **Have emergency procedures** in place

**Mainnet configuration:** Update RPC URL and chain ID (check XRPL docs for mainnet values).

---

## Resources

- **XRPL EVM Docs:** [https://xrpl.org/evm-sidechain.html](https://xrpl.org/evm-sidechain.html)
- **Faucet:** [https://faucet.devnet.xrpl.org/](https://faucet.devnet.xrpl.org/)
- **Explorer:** [https://evm-sidechain.xrpl.org](https://evm-sidechain.xrpl.org)
- **RPC Endpoint:** `https://rpc-evm-sidechain.xrpl.org`
- **Support:** XRPL Discord community

---

## Next Steps

1. ✅ Deploy contracts to XRPL EVM testnet
2. ✅ Test all operations with Python
3. ✅ Integrate with Django views
4. ✅ Set up Celery tasks for async operations
5. ✅ Monitor transactions and events
6. 🚀 Build your application!

**Happy building! 🎉**

