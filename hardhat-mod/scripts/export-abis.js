#!/usr/bin/env node
/**
 * Export ABIs and Contract Addresses to Python Backend
 * 
 * This script copies the contract ABIs and addresses from Hardhat
 * to the Django backend's onchain directory.
 */

import fs from "fs";
import path from "path";

// Paths
const ARTIFACTS_DIR = "./artifacts/contracts";
const DEPLOYMENTS_DIR = "./ignition/deployments/chain-31337";
const BACKEND_ABI_DIR = "../backend/onchain/abi";
const BACKEND_ADDRESSES_FILE = "../backend/onchain/addresses.json";

// Contracts to export
const CONTRACTS = [
  {
    name: "FTCToken",
    artifactPath: path.join(ARTIFACTS_DIR, "FTCToken.sol", "FTCToken.json"),
  },
  {
    name: "CreditTrustToken",
    artifactPath: path.join(ARTIFACTS_DIR, "CreditTrustToken.sol", "CreditTrustToken.json"),
  },
  {
    name: "LoanSystemMVP",
    artifactPath: path.join(ARTIFACTS_DIR, "LoanSystemMVP.sol", "LoanSystemMVP.json"),
  },
];

function ensureDirectoryExists(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
    console.log(`✅ Created directory: ${dirPath}`);
  }
}

function exportABIs() {
  console.log("📦 Exporting ABIs to Python backend...\n");
  
  ensureDirectoryExists(BACKEND_ABI_DIR);

  for (const contract of CONTRACTS) {
    try {
      // Read the artifact
      const artifact = JSON.parse(fs.readFileSync(contract.artifactPath, "utf8"));
      const abi = artifact.abi;

      // Write ABI to backend
      const outputPath = path.join(BACKEND_ABI_DIR, `${contract.name}.json`);
      fs.writeFileSync(outputPath, JSON.stringify(abi, null, 2));
      
      console.log(`✅ Exported ${contract.name} ABI to ${outputPath}`);
    } catch (error) {
      console.error(`❌ Failed to export ${contract.name}:`, error.message);
    }
  }
  console.log();
}

function exportAddresses() {
  console.log("📍 Exporting contract addresses...\n");

  try {
    // Read deployed addresses from Hardhat Ignition
    const deployedAddressesPath = path.join(DEPLOYMENTS_DIR, "deployed_addresses.json");
    
    if (!fs.existsSync(deployedAddressesPath)) {
      console.warn("⚠️  No deployed addresses found. Deploy contracts first:");
      console.warn("   npx hardhat ignition deploy ignition/modules/LoanSystemFullModule.ts --network localhost\n");
      return;
    }

    const deployedAddresses = JSON.parse(fs.readFileSync(deployedAddressesPath, "utf8"));

    // Map to simpler names for Python backend
    const addresses = {
      FTCToken: deployedAddresses["LoanSystemFullModule#FTCToken"] || "",
      CreditTrustToken: deployedAddresses["LoanSystemFullModule#CreditTrustToken"] || "",
      LoanSystemMVP: deployedAddresses["LoanSystemFullModule#LoanSystemMVP"] || "",
    };

    // Write to backend
    const backendDir = path.dirname(BACKEND_ADDRESSES_FILE);
    ensureDirectoryExists(backendDir);
    
    fs.writeFileSync(BACKEND_ADDRESSES_FILE, JSON.stringify(addresses, null, 2));
    
    console.log(`✅ Exported addresses to ${BACKEND_ADDRESSES_FILE}`);
    console.log("\nDeployed Addresses:");
    Object.entries(addresses).forEach(([name, addr]) => {
      console.log(`   ${name}: ${addr}`);
    });
    console.log();
  } catch (error) {
    console.error("❌ Failed to export addresses:", error.message);
  }
}

function main() {
  console.log("=" .repeat(60));
  console.log("🚀 ABI and Address Exporter for Python Backend");
  console.log("=" .repeat(60) + "\n");

  exportABIs();
  exportAddresses();

  console.log("=" .repeat(60));
  console.log("✅ Export complete!");
  console.log("\n📚 Next steps:");
  console.log("   1. Update your .env file with Web3 configuration");
  console.log("   2. Use the Web3 services in backend/apps/tokens/services/");
  console.log("=" .repeat(60));
}

main();

