pragma solidity ^0.8.20;

/*
  Overview (for this PR):
  - Simple deposit/withdraw pool sketch so we have an ABI to point at.
  - The idea is: lenders deposit here; LoanRegistry can ask the pool to fund a loan.

  What we’ll tighten in a follow-up PR (not blocking this one):
  - Send funds directly from the Pool to the Escrow (not to the Registry).
  - Add events for deposits, withdrawals, loan funding, and repayments to help off-chain tracking.
  - Add a basic share accounting model (or ERC4626-style wrapper) so rewards are proportional.
  - Add safety around ETH transfers and reentrancy on withdraw/fund paths.
  - Don’t change totals on "repayment received" until real accounting is in place.
*/



contract LiquidityPool {
    mapping(address => uint256) public deposits;
    uint256 public totalDeposits;
    address public loanRegistry;

    modifier onlyRegistry() {
        require(msg.sender == loanRegistry, "Not authorized");
        _;
    }

    constructor(address _registry) {
        loanRegistry = _registry;
    }

    function deposit() external payable {
        deposits[msg.sender] += msg.value;
        totalDeposits += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(deposits[msg.sender] >= amount, "Insufficient");
        deposits[msg.sender] -= amount;
        totalDeposits -= amount;
        payable(msg.sender).transfer(amount);
    }

    function fundLoan(uint256 loanId, uint256 amount) external onlyRegistry returns (bool) {
        require(amount <= address(this).balance, "Not enough funds");
        payable(msg.sender).transfer(amount); // goes to escrow
        return true;
    }

    function receiveRepayment(uint256 loanId, uint256 amount) external payable onlyRegistry {
        totalDeposits += amount; // simplistic yield handling
    }
}
