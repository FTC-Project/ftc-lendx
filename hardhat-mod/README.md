## Hardhat module for contract development

The hardhat-mod folder contains the Hardhat configuration and smart contract code for the FTCToken used in the FTC LendX platform. It includes 3 main contracts (found in the contracts/ directory):

1. LoanSystemMVP.sol
    - Acts as the core lending protocol logic.
    - Manages the lifecycle of loans: creation, disbursement, repayment, and state transitions.
    - Coordinates with the token contracts (FTCT and CTT) to handle collateral, repayments, and trust/reputation updates.
    - Enforces rules like who can create loans, how repayments are validated, and when trust tokens are awarded.

2. CreditTrustToken.sol
    - An ERC‑20–like “soulbound” reputation token.
    - Non‑transferable: represents a borrower’s creditworthiness rather than spendable currency.
    - Minted or updated by the LoanSystem when borrowers repay loans on time.
    - Provides a transparent, on‑chain reputation system that lenders can reference when deciding to fund future loans.

3. FTCToken.sol
    - The fungible stable token used for actual lending and repayment flows.
    - Borrowers receive FTCT when loans are disbursed, and repay in FTCT.
    - Lenders deposit FTCT into the pool, which the LoanSystem then allocates to borrowers.
    - Implements standard ERC‑20 functionality (transfer, approve, allowance) 

***


A few other thinsg to note: the contracts are deployed using hardhat, with the configurations in hardhat.config.ts. There are configurations for different networks, including a localhost network for local testing and development. 

The current deployment scripts can be found under ignition/modules, and is called LoanSystemFullModule.ts, to deploy all 3 contracts and set up the initial state, the command to run the deployment is: 

```bash
npx hardhat run ignition/modules/LoanSystemFullModule.ts --network localhost
```

This deploys the contracts to a local Hardhat network (that needs to already be running, you can easily run a network using npx hardhat node, in a seperate terminal).

All the environment variables needed for deployment (like the admin private key and RPC URL) are stored in the .env.hardhat file.

There is a test.js file under the scripts directory , is a simple cli that allows you to interact with the deployed contracts on the local network. You can create loans, repay them, and check balances using this script. To run it, use: 

```bash
node scripts/test.js
```

***

The CLI also includes commands to mint FTCT tokens directly to lender and borrower wallets. This is required to give accounts an initial balance so they can deposit into the pool or withdraw after loan repayments.

```bash
# Mint FTCT to a lender wallet
node scripts/cli.js mint-ftct <lenderPrivateKey> <amount>

# Mint FTCT to a borrower wallet
node scripts/cli.js mint-ftct <borrowerPrivateKey> <amount>
```
This ensures both lenders and borrowers have the FTCT liquidity needed to interact with the LoanSystem (depositing into the pool, withdrawing, or repaying loans).