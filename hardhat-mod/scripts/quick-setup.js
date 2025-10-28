#!/usr/bin/env node
/**
 * Quick Setup Script
 * Automates the process of minting tokens and funding the loan system
 */

import { ethers } from "ethers";
import * as dotenv from "dotenv";
import fs from "fs";
import path from "path";

// Load environment
dotenv.config({ path: path.resolve(process.cwd(), ".env.hardhat") });

const {
  RPC_URL,
  FTCT_ADDRESS,
  LOAN_ADDRESS,
  ADMIN_PRIVATE_KEY,
  ADMIN_PUBLIC_KEY,
  LENDER_PRIVATE_KEY,
  LENDER_PUBLIC_KEY,
  BORROWER_PRIVATE_KEY,
  BORROWER_PUBLIC_KEY,
} = process.env;

// Check required variables
if (!RPC_URL || !FTCT_ADDRESS || !LOAN_ADDRESS || !ADMIN_PRIVATE_KEY) {
  console.error("❌ Missing required environment variables in .env.hardhat");
  console.error("Please create .env.hardhat from .env.hardhat.example");
  process.exit(1);
}

const provider = new ethers.JsonRpcProvider(RPC_URL);

// Load ABIs
const ftcTokenAbi = JSON.parse(
  fs.readFileSync("./artifacts/contracts/FTCToken.sol/FTCToken.json", "utf8")
).abi;

const loanSystemAbi = JSON.parse(
  fs.readFileSync("./artifacts/contracts/LoanSystemMVP.sol/LoanSystemMVP.json", "utf8")
).abi;

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Helper function to send transaction with proper nonce management
async function sendTransactionWithRetry(txPromise, description, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const tx = await txPromise();
      const receipt = await tx.wait();
      
      // Add small delay to ensure nonce updates propagate
      await sleep(500);
      
      return { tx, receipt };
    } catch (error) {
      if (error.code === 'NONCE_EXPIRED' && i < maxRetries - 1) {
        console.log(`   ⚠️  Nonce conflict, retrying ${description}... (attempt ${i + 2}/${maxRetries})`);
        await sleep(1000); // Wait longer before retry
        continue;
      }
      throw error;
    }
  }
}

async function main() {
  console.log("🚀 Quick Setup Script for LoanSystemMVP\n");
  console.log("=" .repeat(60));

  // Create wallet instances
  const adminWallet = new ethers.Wallet(ADMIN_PRIVATE_KEY, provider);
  const ftcToken = new ethers.Contract(FTCT_ADDRESS, ftcTokenAbi, adminWallet);
  const loanSystem = new ethers.Contract(LOAN_ADDRESS, loanSystemAbi, adminWallet);

  console.log("📋 Configuration:");
  console.log(`   Admin: ${adminWallet.address}`);
  console.log(`   FTCToken: ${FTCT_ADDRESS}`);
  console.log(`   LoanSystem: ${LOAN_ADDRESS}`);
  if (LENDER_PUBLIC_KEY) console.log(`   Lender #1: ${LENDER_PUBLIC_KEY}`);
  if (BORROWER_PUBLIC_KEY) console.log(`   Borrower #1: ${BORROWER_PUBLIC_KEY}`);
  console.log("=" .repeat(60) + "\n");

  try {
    // Step 1: Check current balances
    console.log("📊 Step 1: Checking current balances...");
    const adminBalance = await ftcToken.balanceOf(adminWallet.address);
    console.log(`   Admin FTCT balance: ${ethers.formatEther(adminBalance)}`);

    if (LENDER_PUBLIC_KEY) {
      const lender1Balance = await ftcToken.balanceOf(LENDER_PUBLIC_KEY);
      console.log(`   Lender #1 FTCT balance: ${ethers.formatEther(lender1Balance)}`);
    }

    if (BORROWER_PUBLIC_KEY) {
      const borrower1Balance = await ftcToken.balanceOf(BORROWER_PUBLIC_KEY);
      console.log(`   Borrower #1 FTCT balance: ${ethers.formatEther(borrower1Balance)}`);
    }

    const poolBalance = await loanSystem.totalPool();
    console.log(`   Pool total: ${ethers.formatEther(poolBalance)}\n`);

    // Step 2: Mint tokens if needed
    console.log("💰 Step 2: Minting tokens...");
    
    // Mint to admin if low
    if (adminBalance < ethers.parseEther("1000")) {
      console.log("   Minting 10,000 FTCT to Admin...");
      const result = await sendTransactionWithRetry(
        () => ftcToken.mint(adminWallet.address, ethers.parseEther("10000")),
        "mint to Admin"
      );
      console.log(`   ✅ Minted to Admin (tx: ${result.tx.hash})`);
    } else {
      console.log("   ✓ Admin already has sufficient balance");
    }

    // Mint to lender if provided
    if (LENDER_PUBLIC_KEY && LENDER_PRIVATE_KEY) {
      const lender1Balance = await ftcToken.balanceOf(LENDER_PUBLIC_KEY);
      if (lender1Balance < ethers.parseEther("1000")) {
        console.log("   Minting 5,000 FTCT to Lender #1...");
        const result = await sendTransactionWithRetry(
          () => ftcToken.mint(LENDER_PUBLIC_KEY, ethers.parseEther("5000")),
          "mint to Lender #1"
        );
        console.log(`   ✅ Minted to Lender #1 (tx: ${result.tx.hash})`);
      } else {
        console.log("   ✓ Lender #1 already has sufficient balance");
      }
    }

    // Mint to borrower if provided
    if (BORROWER_PUBLIC_KEY && BORROWER_PRIVATE_KEY) {
      const borrower1Balance = await ftcToken.balanceOf(BORROWER_PUBLIC_KEY);
      if (borrower1Balance < ethers.parseEther("500")) {
        console.log("   Minting 2,000 FTCT to Borrower #1...");
        const result = await sendTransactionWithRetry(
          () => ftcToken.mint(BORROWER_PUBLIC_KEY, ethers.parseEther("2000")),
          "mint to Borrower #1"
        );
        console.log(`   ✅ Minted to Borrower #1 (tx: ${result.tx.hash})`);
      } else {
        console.log("   ✓ Borrower #1 already has sufficient balance");
      }
    }
    console.log();

    // Step 3: Fund the pool
    console.log("🏦 Step 3: Funding the pool...");
    
    if (LENDER_PRIVATE_KEY && LENDER_PUBLIC_KEY) {
      const lenderWallet = new ethers.Wallet(LENDER_PRIVATE_KEY, provider);
      const ftcTokenAsLender = new ethers.Contract(FTCT_ADDRESS, ftcTokenAbi, lenderWallet);
      const loanSystemAsLender = new ethers.Contract(LOAN_ADDRESS, loanSystemAbi, lenderWallet);
      
      const currentShares = await loanSystem.sharesOf(LENDER_PUBLIC_KEY);
      
      if (currentShares < ethers.parseEther("100")) {
        const depositAmount = ethers.parseEther("2000");
        console.log(`   Approving ${ethers.formatEther(depositAmount)} FTCT for LoanSystem...`);
        const approveResult = await sendTransactionWithRetry(
          () => ftcTokenAsLender.approve(LOAN_ADDRESS, depositAmount),
          "approve tokens"
        );
        console.log(`   ✅ Approved (tx: ${approveResult.tx.hash})`);

        console.log(`   Depositing ${ethers.formatEther(depositAmount)} FTCT to pool...`);
        const depositResult = await sendTransactionWithRetry(
          () => loanSystemAsLender.depositFTCT(depositAmount),
          "deposit to pool"
        );
        console.log(`   ✅ Deposited (tx: ${depositResult.tx.hash})`);

        const newShares = await loanSystem.sharesOf(LENDER_PUBLIC_KEY);
        console.log(`   Lender #1 shares: ${ethers.formatEther(newShares)}`);
      } else {
        console.log("   ✓ Lender #1 already has shares in the pool");
      }
    } else {
      console.log("   ⚠️  No lender wallet configured - skipping pool funding");
    }
    console.log();

    // Step 4: Summary
    console.log("=" .repeat(60));
    console.log("✅ Setup Complete!\n");
    console.log("📊 Final Balances:");
    
    const finalAdminBalance = await ftcToken.balanceOf(adminWallet.address);
    console.log(`   Admin FTCT: ${ethers.formatEther(finalAdminBalance)}`);

    if (LENDER_PUBLIC_KEY) {
      const finalLender1Balance = await ftcToken.balanceOf(LENDER_PUBLIC_KEY);
      const finalLender1Shares = await loanSystem.sharesOf(LENDER_PUBLIC_KEY);
      console.log(`   Lender #1 FTCT: ${ethers.formatEther(finalLender1Balance)}`);
      console.log(`   Lender #1 Shares: ${ethers.formatEther(finalLender1Shares)}`);
    }

    if (BORROWER_PUBLIC_KEY) {
      const finalBorrower1Balance = await ftcToken.balanceOf(BORROWER_PUBLIC_KEY);
      console.log(`   Borrower #1 FTCT: ${ethers.formatEther(finalBorrower1Balance)}`);
    }

    const finalPoolBalance = await loanSystem.totalPool();
    const totalShares = await loanSystem.totalShares();
    console.log(`   Pool Total: ${ethers.formatEther(finalPoolBalance)} FTCT`);
    console.log(`   Total Shares: ${ethers.formatEther(totalShares)}`);

    console.log("\n🎉 Your system is now ready!");
    console.log("\n📚 Next steps:");
    console.log("   1. Create a loan: node scripts/cli.js create-loan <borrower> <amount> <aprBps> <termDays> <adminPrivateKey>");
    console.log("   2. Fund the loan: node scripts/cli.js fund-loan <loanId> <adminPrivateKey>");
    console.log("   3. Disburse to borrower: node scripts/cli.js disburse-loan-ftct <loanId> <adminPrivateKey>");
    console.log("   4. See all commands: node scripts/cli.js --help");
    console.log("\n📖 For detailed guide, see: SETUP_GUIDE.md");
    console.log("=" .repeat(60));

  } catch (error) {
    console.error("\n❌ Error during setup:");
    console.error(error);
    process.exit(1);
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

