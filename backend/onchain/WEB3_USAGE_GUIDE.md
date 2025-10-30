# Python Web3 Integration Guide

This guide shows you how to interact with your smart contracts using Python and Web3.py in your Django backend.

## Table of Contents
1. [Setup](#setup)
2. [Configuration](#configuration)
3. [Usage Examples](#usage-examples)
4. [XRPL EVM Testnet Configuration](#xrpl-evm-testnet-configuration)
5. [Django Integration](#django-integration)

---

## Setup

### 1. Export ABIs from Hardhat

First, export the contract ABIs from your Hardhat project:

```bash
cd hardhat-mod
node scripts/export-abis.js
```

This will copy ABIs to `backend/onchain/abi/` and addresses to `backend/onchain/addresses.json`.

### 2. Configure Environment Variables

Add these to your `.env` file:

```env
# Web3 Configuration
WEB3_PROVIDER_URL=http://127.0.0.1:8545  # Or XRPL EVM testnet URL
ADMIN_ADDRESS=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
ADMIN_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

# Contract Addresses (from hardhat-mod/ignition/deployments/.../deployed_addresses.json)
FTCTOKEN_ADDRESS=0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512
CREDITTRUST_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3
LOANSYSTEM_ADDRESS=0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0
```

### 3. Install Dependencies

Ensure `web3` is installed:

```bash
pip install web3>=6.0
```

---

## Configuration

The Web3 services are configured via Django settings. Settings are automatically loaded from environment variables or use defaults for local development.

### Key Settings (backend/settings/base.py)

- `WEB3_PROVIDER_URL`: RPC endpoint
- `ADMIN_ADDRESS`: Admin wallet address
- `ADMIN_PRIVATE_KEY`: Admin wallet private key
- `FTCTOKEN_ADDRESS`: FTCToken contract address
- `CREDITTRUST_ADDRESS`: CreditTrustToken contract address
- `LOANSYSTEM_ADDRESS`: LoanSystemMVP contract address
- `*_ABI_PATH`: Paths to ABI JSON files

---

## Usage Examples

### Import Services

```python
from backend.apps.tokens.services import (
    FTCTokenService,
    LoanSystemService,
    CreditTrustTokenService,
)
```

---

### FTCToken Operations

#### 1. Mint Tokens (Admin Only)

```python
# Initialize service
ftc_service = FTCTokenService()

# Mint 1000 FTCT to a lender
result = ftc_service.mint(
    to_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    amount=1000.0,  # 1000 FTCT
)

print(f"Minted! Tx: {result['tx_hash']}")
print(f"Gas used: {result['gas_used']}")
```

#### 2. Check Balance

```python
balance = ftc_service.get_balance("0x70997970C51812dc3A010C7d01b50e0d17dc79C8")
print(f"Balance: {balance} FTCT")
```

#### 3. Transfer Tokens

```python
result = ftc_service.transfer(
    from_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    to_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
    amount=100.0,
    private_key="0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
)
print(f"Transferred! Tx: {result['tx_hash']}")
```

#### 4. Approve Spending

```python
# Approve LoanSystem to spend tokens
from django.conf import settings

result = ftc_service.approve(
    owner_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    spender_address=settings.LOANSYSTEM_ADDRESS,
    amount=500.0,
    private_key="0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
)
print(f"Approved! Tx: {result['tx_hash']}")
```

#### 5. Check Allowance

```python
allowance = ftc_service.get_allowance(
    owner="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    spender=settings.LOANSYSTEM_ADDRESS,
)
print(f"Allowance: {allowance} FTCT")
```

---

### LoanSystem Operations

#### 1. Deposit FTCT (Lender)

```python
loan_service = LoanSystemService()

# First approve (see FTCToken approve example above)
# Then deposit
result = loan_service.deposit_ftct(
    lender_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    amount=500.0,
    lender_private_key="0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
)

print(f"Deposited! Tx: {result['tx_hash']}")

# Check shares
shares = loan_service.get_shares_of("0x70997970C51812dc3A010C7d01b50e0d17dc79C8")
print(f"Lender shares: {shares}")
```

#### 2. Withdraw FTCT (Lender)

```python
# Withdraw by redeeming shares
result = loan_service.withdraw_ftct(
    lender_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    share_amount=100.0,  # Number of shares to redeem
    lender_private_key="0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
)

print(f"Withdrew {result['ftct_amount']} FTCT! Tx: {result['tx_hash']}")
```

#### 3. Create Loan (Admin)

```python
# Create a loan for a borrower
loan_id, result = loan_service.create_loan(
    borrower_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
    amount=200.0,  # 200 FTCT
    apr_bps=1200,  # 12% APR
    term_days=30,  # 30 days
)

print(f"Created loan ID {loan_id}! Tx: {result['tx_hash']}")
```

#### 4. Fund and Disburse Loan (Admin)

```python
# Fund the loan (reserves pool funds)
result = loan_service.mark_funded(loan_id=loan_id)
print(f"Loan funded! Tx: {result['tx_hash']}")

# Disburse to borrower
result = loan_service.mark_disbursed_ftct(loan_id=loan_id)
print(f"Loan disbursed! Tx: {result['tx_hash']}")
```

#### 5. Repay Loan (Borrower)

```python
# Calculate repayment amount
loan_details = loan_service.get_loan(loan_id)
interest = loan_service.calculate_interest(
    principal=float(loan_details['principal']),
    apr_bps=loan_details['apr_bps'],
    term_days=loan_details['term_days'],
)
total_due = loan_details['principal'] + interest

print(f"Principal: {loan_details['principal']} FTCT")
print(f"Interest: {interest} FTCT")
print(f"Total due: {total_due} FTCT")

# First approve LoanSystem to spend tokens (borrower approves)
ftc_service.approve(
    owner_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
    spender_address=settings.LOANSYSTEM_ADDRESS,
    amount=float(total_due),
    private_key="0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
)

# Repay the loan
result = loan_service.mark_repaid_ftct(
    loan_id=loan_id,
    on_time=True,
    amount=float(total_due),
    borrower_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
    borrower_private_key="0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
)

print(f"Loan repaid! Tx: {result['tx_hash']}")
```

#### 6. Default Loan (Admin)

```python
result = loan_service.mark_defaulted(loan_id=loan_id)
print(f"Loan defaulted! Tx: {result['tx_hash']}")
```

#### 7. Query Pool Status

```python
total_pool = loan_service.get_total_pool()
total_shares = loan_service.get_total_shares()

print(f"Total pool: {total_pool} FTCT")
print(f"Total shares: {total_shares}")
```

---

### CreditTrustToken Operations

#### 1. Check Balance

```python
ctt_service = CreditTrustTokenService()

balance = ctt_service.get_balance("0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC")
print(f"CreditTrust balance: {balance}")
```

#### 2. Initialize User

```python
result = ctt_service.initialize_user(
    user_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
    initial_score=0,
)
print(f"User initialized! Tx: {result['tx_hash']}")
```

#### 3. Mint Reputation (Admin)

```python
result = ctt_service.mint(
    user_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
    amount=100,  # 100 reputation points
)
print(f"Minted reputation! Tx: {result['tx_hash']}")
```

#### 4. Burn Reputation (Admin)

```python
result = ctt_service.burn(
    user_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
    amount=50,  # 50 reputation points
)
print(f"Burned reputation! Tx: {result['tx_hash']}")
```

---

### Event Queries

#### Get Transfer Events

```python
# Get all transfers to an address
events = ftc_service.get_transfer_events(
    from_block=0,
    to_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
)

for event in events:
    print(f"Block {event['blockNumber']}: {event['args']['value']} FTCT")
```

#### Get Loan Events

```python
# Get all loans for a borrower
events = loan_service.get_loan_created_events(
    from_block=0,
    borrower="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
)

for event in events:
    args = event['args']
    print(f"Loan {args['id']}: {args['principal']} FTCT")
```

---

## XRPL EVM Testnet Configuration

To deploy and use your contracts on the XRPL EVM Testnet:

### 1. Update Environment Variables

```env
# XRPL EVM Testnet
WEB3_PROVIDER_URL=https://rpc-evm-sidechain.xrpl.org

# Your admin wallet (NOT the hardhat test account!)
ADMIN_ADDRESS=0xYourWalletAddress
ADMIN_PRIVATE_KEY=0xYourPrivateKey

# Contract addresses after deployment to XRPL EVM
FTCTOKEN_ADDRESS=0xDeployedFTCTokenAddress
CREDITTRUST_ADDRESS=0xDeployedCreditTrustAddress
LOANSYSTEM_ADDRESS=0xDeployedLoanSystemAddress
```

### 2. Get Testnet Funds

1. Visit the [XRPL EVM Faucet](https://faucet.devnet.xrpl.org/)
2. Enter your wallet address
3. Request test tokens

### 3. Deploy Contracts to XRPL EVM

Update `hardhat-mod/.env.hardhat`:

```env
RPC_URL=https://rpc-evm-sidechain.xrpl.org
ADMIN_PRIVATE_KEY=0xYourPrivateKey
ADMIN_PUBLIC_KEY=0xYourWalletAddress
```

Deploy:

```bash
cd hardhat-mod
npx hardhat ignition deploy ignition/modules/LoanSystemFullModule.ts --network localhost
```

### 4. Export ABIs and Update Backend

```bash
cd hardhat-mod
node scripts/export-abis.js
```

Update your Django `.env` with the new contract addresses.

### 5. Test Connection

```python
from backend.apps.tokens.services import FTCTokenService

ftc_service = FTCTokenService()
print(f"Connected to: {ftc_service.web3.provider.endpoint_uri}")
print(f"Chain ID: {ftc_service.web3.eth.chain_id}")
print(f"Block number: {ftc_service.get_block_number()}")
```

---

## Django Integration

### In Views

```python
from django.http import JsonResponse
from backend.apps.tokens.services import FTCTokenService, LoanSystemService

def mint_tokens_view(request):
    """Admin view to mint tokens"""
    address = request.POST.get('address')
    amount = float(request.POST.get('amount'))
    
    ftc_service = FTCTokenService()
    result = ftc_service.mint(address, amount)
    
    return JsonResponse({
        'success': True,
        'tx_hash': result['tx_hash'],
        'block_number': result['block_number'],
    })

def user_balance_view(request, address):
    """Get user's FTCT balance"""
    ftc_service = FTCTokenService()
    balance = ftc_service.get_balance(address)
    
    return JsonResponse({
        'address': address,
        'balance': float(balance),
    })
```

### In Celery Tasks

```python
from celery import shared_task
from backend.apps.tokens.services import LoanSystemService
import logging

logger = logging.getLogger(__name__)

@shared_task
def disburse_loan_async(loan_id):
    """Asynchronously disburse a loan"""
    try:
        loan_service = LoanSystemService()
        result = loan_service.mark_disbursed_ftct(loan_id)
        
        logger.info(f"Disbursed loan {loan_id}: {result['tx_hash']}")
        return {'success': True, 'tx_hash': result['tx_hash']}
    except Exception as e:
        logger.error(f"Failed to disburse loan {loan_id}: {e}")
        return {'success': False, 'error': str(e)}
```

### In Management Commands

```python
from django.core.management.base import BaseCommand
from backend.apps.tokens.services import FTCTokenService

class Command(BaseCommand):
    help = 'Mint FTCT tokens to multiple addresses'
    
    def add_arguments(self, parser):
        parser.add_argument('--addresses', nargs='+', type=str)
        parser.add_argument('--amount', type=float, default=1000.0)
    
    def handle(self, *args, **options):
        ftc_service = FTCTokenService()
        
        for address in options['addresses']:
            try:
                result = ftc_service.mint(address, options['amount'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Minted {options['amount']} FTCT to {address}"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Failed for {address}: {e}")
                )
```

---

## Error Handling

Always wrap contract calls in try-except blocks:

```python
from web3.exceptions import ContractLogicError, TimeExhausted

try:
    result = ftc_service.mint(address, amount)
except ContractLogicError as e:
    # Contract reverted (e.g., "Unauthorized: not admin")
    print(f"Contract error: {e}")
except TimeExhausted:
    # Transaction timeout
    print("Transaction timed out")
except Exception as e:
    # Other errors
    print(f"Unexpected error: {e}")
```

---

## Best Practices

1. **Always check balances** before transfers
2. **Approve before transferring** ERC20 tokens to contracts
3. **Use Celery tasks** for on-chain operations (they can be slow)
4. **Log all transactions** with tx hash and block number
5. **Monitor gas prices** on mainnet (less concern on testnet)
6. **Cache read operations** to reduce RPC calls
7. **Handle transaction failures** gracefully

---

## Troubleshooting

### "Failed to connect to Web3 provider"
- Check `WEB3_PROVIDER_URL` is correct
- Ensure Hardhat node is running (for local dev)
- Verify network connectivity (for XRPL EVM)

### "Insufficient funds"
- Mint more FTCT tokens
- Request testnet tokens from faucet (for XRPL EVM)

### "Execution reverted: Unauthorized"
- Check you're using the correct admin private key
- Verify contract ownership

### "Nonce too low"
- Transaction already sent with that nonce
- Wait for pending transactions to complete

---

## Next Steps

1. Review the example scripts in `backend/onchain/examples/`
2. Integrate services into your Django views and Celery tasks
3. Test locally with Hardhat before deploying to XRPL EVM
4. Set up monitoring and logging for production

For more examples, see `backend/onchain/examples/complete_workflow.py`.

