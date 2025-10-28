import type { HardhatUserConfig } from "hardhat/config";

import hardhatToolboxViemPlugin from "@nomicfoundation/hardhat-toolbox-viem";
import { configVariable } from "hardhat/config";

import * as dotenv from "dotenv";
dotenv.config({ path: ".env.hardhat" });



const config: HardhatUserConfig = {
  plugins: [hardhatToolboxViemPlugin],
  solidity: {
    profiles: {
      default: {
        version: "0.8.28",
      },
      production: {
        version: "0.8.28",
        settings: {
          optimizer: {
            enabled: true,
            runs: 200,
          },
        },
      },
    },
  },
  networks: {
    localhost: {
      type: "http",
      chainType: "l1",
      url: process.env.RPC_URL!,
      accounts: [process.env.ADMIN_PRIVATE_KEY!],
    },
    xrpl_evm_testnet: {
      type: "http",
      url: process.env.RPC_URL!,
      accounts: [process.env.ADMIN_PRIVATE_KEY!],
      chainId: 1449000,
    },
  },
};

export default config;
