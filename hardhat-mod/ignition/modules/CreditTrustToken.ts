import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("CreditTrustTokenModule", (m) => {
  // Use a parameter for the admin address
  const admin = m.getParameter("admin", "0x0000000000000000000000000000000000000001");

  // Define the contract deployment
  const ctt = m.contract("CreditTrustToken", [admin]);

  // Return the contract future so Ignition knows what to deploy
  return { ctt };
});