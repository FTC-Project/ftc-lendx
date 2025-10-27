import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";
import * as dotenv from "dotenv";
dotenv.config({ path: ".env.hardhat" }); // load your env file

export default buildModule("LoanSystemFullModule", (m) => {
  // Admin address from .env, fallback to a default if not set
  const admin = m.getParameter("admin", process.env.ADMIN_PUBLIC_KEY);

  if (!admin) throw new Error("ADMIN_PUBLIC_KEY must be set in .env.hardhat");

  // Deploy CreditTrustToken first
  const ctt = m.contract("CreditTrustToken", [admin]);

  // Deploy FTCT
  const stable = m.contract("FTCToken", [admin]);

  // Deploy LoanSystemMVP, passing in admin and the CTT + FTCT futures
  const loan = m.contract("LoanSystemMVP", [admin, ctt, stable]);

  // 🔑 Post-deployment wiring:
  // Tell CTT which LoanSystem to trust
  m.call(ctt, "setLoanSystem", [loan]);

  // Return all three so Ignition knows to deploy them
  return { ctt, stable, loan };
});