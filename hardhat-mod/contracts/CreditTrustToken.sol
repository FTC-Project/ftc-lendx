pragma solidity ^0.8.20;

/**
 * @title CreditTrustToken (Soulbound Reputation Token)
 * @notice Non-transferable ERC-like token that tracks borrower reputation.
 *         Balances can go negative (int256). Only admin (LoanManager) can mint/burn.
 */
contract CreditTrustToken {
    mapping(address => int256) public tokenBalance;
    mapping(address => bool) public isInitialized;

    address public admin;
    address public loanSystem; // <- new trusted contract

    event UserInitialized(address indexed user, int256 initialTrustScore);
    event Minted(address indexed user, uint256 amount, int256 newBalance);
    event Burned(address indexed user, uint256 amount, int256 newBalance);

    modifier onlyAdmin() {
        require(msg.sender == admin, "Unauthorized: not admin");
        _;
    }

    modifier onlyAdminOrLoanSystem() {
        require(
            msg.sender == admin || msg.sender == loanSystem,
            "Unauthorized: not admin or loan system"
        );
        _;
    }

    constructor(address _admin) {
        require(_admin != address(0), "Admin cannot be zero");
        admin = _admin;
    }

    /// @notice One-time setup by admin to authorize the LoanSystem contract
    function setLoanSystem(address _loanSystem) external onlyAdmin {
        require(_loanSystem != address(0), "LoanSystem cannot be zero");
        loanSystem = _loanSystem;
    }


    function initializeUser(address user, uint256 initialTrustScore) external onlyAdminOrLoanSystem {
        require(user != address(0), "Invalid user");
        require(!isInitialized[user], "Already initialized");
        require(initialTrustScore <= uint256(type(int256).max), "Score too large");

        int256 initScore = int256(initialTrustScore);
        tokenBalance[user] = initScore;
        isInitialized[user] = true;

        emit UserInitialized(user, initScore);
    }

    function mint(address user, uint256 amount) external onlyAdminOrLoanSystem {
        require(user != address(0), "Invalid user");
        require(amount > 0, "Amount must be > 0");
        require(amount <= uint256(type(int256).max), "Amount too large");

        int256 newBalance = tokenBalance[user] + int256(amount);
        tokenBalance[user] = newBalance;

        emit Minted(user, amount, newBalance);
    }

    function burn(address user, uint256 amount) external onlyAdminOrLoanSystem {
        require(user != address(0), "Invalid user");
        require(amount > 0, "Amount must be > 0");
        require(amount <= uint256(type(int256).max), "Amount too large");

        int256 newBalance = tokenBalance[user] - int256(amount);
        tokenBalance[user] = newBalance;

        emit Burned(user, amount, newBalance);
    }

    // Optional: allow admin rotation if LoanManager is upgraded
    function setAdmin(address newAdmin) external onlyAdminOrLoanSystem {
        require(newAdmin != address(0), "Invalid new admin");
        admin = newAdmin;
    }

    // No transfer or approval functions — soulbound by design
}