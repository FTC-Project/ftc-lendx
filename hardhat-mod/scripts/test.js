#!/usr/bin/env node
import { ethers } from "ethers";
import * as dotenv from "dotenv";
import { Command } from "commander";
import fs from "fs";
import path from "path";

// ----------------------------
// Load environment variables
// ----------------------------
dotenv.config({ path: path.resolve(process.cwd(), ".env.hardhat") });

const {
  RPC_URL,
  CTT_ADDRESS,
  LOAN_ADDRESS,
  FTCT_ADDRESS, // new ERC20 token address
} = process.env;

if (!RPC_URL || !CTT_ADDRESS || !LOAN_ADDRESS || !FTCT_ADDRESS) {
  console.error("❌ Missing required environment variables in .env.hardhat");
  process.exit(1);
}

const provider = new ethers.JsonRpcProvider(RPC_URL);
const program = new Command();

// ----------------------------
// Load ABIs
// ----------------------------
const loanSystemAbi = JSON.parse(
  fs.readFileSync("./artifacts/contracts/LoanSystemMVP.sol/LoanSystemMVP.json", "utf8")
).abi;

const cttAbi = JSON.parse(
  fs.readFileSync("./artifacts/contracts/CreditTrustToken.sol/CreditTrustToken.json", "utf8")
).abi;

const stableAbi = JSON.parse(
  fs.readFileSync("./artifacts/contracts/FTCToken.sol/FTCToken.json", "utf8")
).abi;

// ---------------- Helper functions ----------------
function getLoanSystemContract(privateKey) {
  const wallet = new ethers.Wallet(privateKey, provider);
  return new ethers.Contract(LOAN_ADDRESS, loanSystemAbi, wallet);
}

function getCTTContract(privateKey) {
  const wallet = new ethers.Wallet(privateKey, provider);
  return new ethers.Contract(CTT_ADDRESS, cttAbi, wallet);
}

function getStableContract(privateKey) {
  const wallet = new ethers.Wallet(privateKey, provider);
  return new ethers.Contract(FTCT_ADDRESS, stableAbi, wallet);
}

// --------------------- Commands ---------------------

// Approve + Deposit FTCT in one go
program
  .command("deposit-ftct <amount> <privateKey>")
  .description("Approve LoanSystem and deposit FTCT tokens into the pool in one step")
  .action(async (amount, privateKey) => {
    try {
      // 1. Approve LoanSystem to spend tokens
      const stable = getStableContract(privateKey);
      const approveTx = await stable.approve(LOAN_ADDRESS, ethers.parseEther(amount));
      console.log("Approve tx:", approveTx.hash);
      await approveTx.wait();
      console.log(`✅ Approved ${amount} FTCT for LoanSystem`);

      // 2. Deposit into LoanSystem
      const loanSystem = getLoanSystemContract(privateKey);
      const depositTx = await loanSystem.depositFTCT(ethers.parseEther(amount));
      console.log("DepositFTCT tx:", depositTx.hash);
      await depositTx.wait();
      console.log(`✅ Deposited ${amount} FTCT into the pool`);
    } catch (err) {
      console.error("❌ Error approving + depositing FTCT:", err);
    }
  });

// Withdraw FTCT shares
program
  .command("withdraw-ftct <shares> <privateKey>")
  .description("Withdraw FTCT tokens by redeeming shares from a wallet")
  .action(async (shares, privateKey) => {
    try {
      const loanSystem = getLoanSystemContract(privateKey);
      const wallet = new ethers.Wallet(privateKey, provider);
      console.log("Using wallet:", wallet.address);

      // Call withdrawFTCT with share amount
      const tx = await loanSystem.withdrawFTCT(ethers.parseUnits(shares, 0));
      console.log("WithdrawFTCT tx:", tx.hash);

      await tx.wait();
      console.log(`Successfully withdrew ${shares} FTCT`);
    } catch (err) {
      console.error("❌ Error withdrawing FTCT:", err);
    }
  });

// Check pool total
program
  .command("pool <privateKey>")
  .description("Query total pool balance")
  .action(async (privateKey) => {
    try {
      const loanSystem = getLoanSystemContract(privateKey);
      const total = await loanSystem.totalPool();
      console.log("Total pool balance (FTCT):", ethers.formatEther(total));
    } catch (err) {
      console.error("❌ Error:", err);
    }
  });

// Check user shares
program
  .command("shares <user> <privateKey>")
  .description("Query shares of a user")
  .action(async (user, privateKey) => {
    try {
      const loanSystem = getLoanSystemContract(privateKey);
      const shares = await loanSystem.sharesOf(user);
      console.log("User shares:", shares.toString());
    } catch (err) {
      console.error("❌ Error:", err);
    }
  });

// Check CreditTrustToken balance
program
  .command("trust <user> <privateKey>")
  .description("Check CreditTrustToken balance of a user")
  .action(async (user, privateKey) => {
    try {
      const ctt = getCTTContract(privateKey);
      const bal = await ctt.tokenBalance(user);
      console.log("Trust balance:", bal.toString());
    } catch (err) {
      console.error("❌ Error:", err);
    }
  });

// ---------------- Loan Commands ----------------

// Create a loan (admin only)
program
  .command("create-loan <borrower> <amount> <aprBps> <termDays> <privateKey>")
  .description("Admin creates a loan entry")
  .action(async (borrower, amount, aprBps, termDays, privateKey) => {
    try {
      const loanSystem = getLoanSystemContract(privateKey);
      const wallet = new ethers.Wallet(privateKey, provider);
      console.log("Using admin wallet:", wallet.address);

      const tx = await loanSystem.createLoan(
        borrower,
        ethers.parseEther(amount),
        parseInt(aprBps),
        parseInt(termDays)
      );
      console.log("CreateLoan tx:", tx.hash);
      const receipt = await tx.wait();

      // Parse LoanCreated event
      const event = receipt.logs.find(l => l.fragment?.name === "LoanCreated");
      if (event) {
        console.log(`Loan created with ID: ${event.args.id.toString()}`);
      }
    } catch (err) {
      console.error("❌ Error:", err);
    }
  });

// Fund a loan (admin only)
program
  .command("fund-loan <loanId> <privateKey>")
  .description("Admin reserves pool funds for a loan (Created → Funded)")
  .action(async (loanId, privateKey) => {
    try {
      const loanSystem = getLoanSystemContract(privateKey);
      const tx = await loanSystem.markFunded(loanId);
      console.log("FundLoan tx:", tx.hash);
      await tx.wait();
      console.log(`Loan ${loanId} marked as Funded`);
    } catch (err) {
      console.error("❌ Error:", err);
    }
  });

  // Disburse a loan (admin only, FTCT-based)
program
  .command("disburse-loan-ftct <loanId> <privateKey>")
  .description("Admin disburses FTCT escrow to borrower (Funded → Disbursed)")
  .action(async (loanId, privateKey) => {
    try {
      const loanSystem = getLoanSystemContract(privateKey);

      // Call the ERC20-based disbursement function
      const tx = await loanSystem.markDisbursedFTCT(loanId);

      console.log("DisburseLoan tx:", tx.hash);
      await tx.wait();
      console.log(`✅ Loan ${loanId} marked as Disbursed (FTCT sent to borrower)`);
    } catch (err) {
      console.error("❌ Error disbursing loan:", err);
    }
  });

// Approve + Repay FTCT in one go
program
  .command("repay-ftct-all <loanId> <onTime> <amount> <privateKey>")
  .description("Approve LoanSystem and repay a loan with FTCT tokens in one step")
  .action(async (loanId, onTime, amount, privateKey) => {
    try {
      // 1. Approve LoanSystem to spend repayment amount
      const stable = getStableContract(privateKey); // FTCToken contract
      const approveTx = await stable.approve(LOAN_ADDRESS, ethers.parseEther(amount));
      console.log("Approve tx:", approveTx.hash);
      await approveTx.wait();
      console.log(`✅ Approved ${amount} FTCT for LoanSystem`);

      // 2. Call LoanSystem repayment
      const loanSystem = getLoanSystemContract(privateKey);
      const repayTx = await loanSystem.markRepaidFTCT(
        loanId,
        onTime === "true",
        ethers.parseEther(amount)
      );
      console.log("RepayFTCT tx:", repayTx.hash);
      await repayTx.wait();
      console.log(`✅ Loan ${loanId} repaid with ${amount} FTCT (onTime=${onTime})`);
    } catch (err) {
      console.error("❌ Error approving + repaying FTCT:", err);
    }
  });

// Default a loan (admin only)
program
  .command("default-loan <loanId> <privateKey>")
  .description("Admin marks a loan as defaulted (Disbursed → Defaulted)")
  .action(async (loanId, privateKey) => {
    try {
      const loanSystem = getLoanSystemContract(privateKey);
      const tx = await loanSystem.markDefaulted(loanId);
      console.log("DefaultLoan tx:", tx.hash);
      await tx.wait();
      console.log(`Loan ${loanId} marked as Defaulted`);
    } catch (err) {
      console.error("❌ Error:", err);
    }
  });

// Get all loans (read-only, no key required)
program
  .command("get-loans")
  .description("List all loans and their details")
  .action(async () => {
    try {
      const loanSystem = new ethers.Contract(LOAN_ADDRESS, loanSystemAbi, provider);
      const total = await loanSystem.nextId();
      console.log(`Total loans: ${total.toString()}`);

      const stateMap = ["Created", "Funded", "Disbursed", "Repaid", "Defaulted"];

      for (let i = 0; i < total; i++) {
        const ln = await loanSystem.loans(i);
        console.log(`\nLoan ID: ${i}`);
        console.log(`  Borrower: ${ln.borrower}`);
        console.log(`  Principal: ${ethers.formatEther(ln.principal)} FTCT`);
        console.log(`  APR (bps): ${ln.aprBps}`);
        console.log(`  Term (days): ${ln.termDays}`);
        console.log(`  State: ${stateMap[ln.state] ?? ln.state}`);
        console.log(`  Escrow Balance: ${ethers.formatEther(ln.escrowBalance)} FTCT`);
        console.log(`  Due Date: ${ln.dueDate.toString()}`);
      }
    } catch (err) {
      console.error("❌ Error:", err);
    }
  });

  // Mint FTCT (admin only)
program
  .command("mint-token <to> <amount> <privateKey>")
  .description("Admin mints StableToken to a specified address")
  .action(async (to, amount, privateKey) => {
    try {
      const stable = getStableContract(privateKey);
      const wallet = new ethers.Wallet(privateKey, provider);
      console.log("Using admin wallet:", wallet.address);

      const tx = await stable.mint(to, ethers.parseEther(amount));
      console.log("Mint tx:", tx.hash);
      const receipt = await tx.wait();
      console.log(`Minted ${amount} FTCT to ${to} in block ${receipt.blockNumber}`);
    } catch (err) {
      console.error("❌ Error:", err);
    }
  });

// Check FTCT balance of any address
program
  .command("token-balance <address> <privateKey>")
  .description("Check the FTCT token balance of a given address")
  .action(async (address, privateKey) => {
    try {
      const stable = getStableContract(privateKey);
      const bal = await stable.balanceOf(address);
      console.log(
        `💰 Balance of ${address}: ${ethers.formatEther(bal)} FTCT`
      );
    } catch (err) {
      console.error("❌ Error fetching balance:", err);
    }
  });

program.parse(process.argv);