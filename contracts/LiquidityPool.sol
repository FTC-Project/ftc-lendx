pragma solidity ^0.8.20;

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
