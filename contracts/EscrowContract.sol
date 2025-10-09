pragma solidity ^0.8.20;

/*
  Overview (for this PR):
  - Single escrow contract that keeps per-loan records (mapping by loanId).
  - LoanRegistry is the only caller; users don't call this directly.
  - Current functions show the shape of the API (lock -> release -> repay), not final money movement.

  What we’ll tighten in a follow-up PR (not blocking this one):
  - Actually move ETH in/out of escrow (make the relevant functions payable and check msg.value).
  - Emit events like EscrowFunded / EscrowReleased / EscrowRepaid so indexers can track flows.
  - Add basic safety: reentrancy guard and use low-level call{} for sends instead of transfer().
  - Validate amounts and one-time release (e.g., don’t release twice; make sure funded >= amount).
*/



contract EscrowContract {
    struct EscrowData {
        address lender;
        address borrower;
        uint256 amount;
        bool released;
    }

    mapping(uint256 => EscrowData) public escrows;
    address public loanRegistry;

    modifier onlyRegistry() {
        require(msg.sender == loanRegistry, "Unauthorized");
        _;
    }

    constructor(address _registry) {
        loanRegistry = _registry;
    }

    function lockFunds(uint256 loanId, address lender, uint256 amount) external payable onlyRegistry {
        escrows[loanId] = EscrowData(lender, address(0), amount, false);
    }

    function releaseToBorrower(uint256 loanId, address borrower) external onlyRegistry {
        EscrowData storage esc = escrows[loanId];
        esc.borrower = borrower;
        esc.released = true;
        payable(borrower).transfer(esc.amount);
    }

    function repay(uint256 loanId, uint256 amount) external payable onlyRegistry {
        EscrowData storage esc = escrows[loanId];
        payable(esc.lender).transfer(amount);
    }
}
