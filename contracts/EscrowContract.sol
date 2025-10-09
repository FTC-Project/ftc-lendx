pragma solidity ^0.8.20;

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
