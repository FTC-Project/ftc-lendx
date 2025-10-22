pragma solidity ^0.8.20;

//import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
/*
  Overview (for this PR):
  - This is a simple, non-transferable "credit badge" NFT that we mint after a borrower repays.
  - The tokenURI is a placeholder for now.

  What we’ll tighten in a follow-up PR (not blocking this one):
  - Make it truly "soulbound": block approvals and regular transfers; allow only admin burn for disputes.
  - Store/track a borrower "score" (e.g., +1 per successful repayment) and expose it for reads.
  - Replace the static tokenURI with borrower-specific metadata (e.g., IPFS per borrower or on-chain JSON).
  - Only the LoanRegistry should be allowed to mint.
*/

/*
I had to change this contract quite a lot.
 - it now uses ERC-20 tokens instead of ERC-721 (which are unique NFTs)
*/

/**
 * @title CreditTrustToken (Soulbound Reputation Token)
 * @notice Non-transferable ERC-like token that tracks borrower reputation.
 *         Balances can go negative (int256). Only admin (LoanManager) can mint/burn.
 */
contract CreditTrustToken {
    mapping(address => int256) public tokenBalance;
    mapping(address => bool) public isInitialized;
    address public admin;

    event UserInitialized(address indexed user, int256 initialTrustScore);
    event Minted(address indexed user, uint256 amount, int256 newBalance);
    event Burned(address indexed user, uint256 amount, int256 newBalance);

    modifier onlyAdmin() {
        require(msg.sender == admin, "Unauthorized: not admin");
        _;
    }

    constructor(address _admin) {
        require(_admin != address(0), "Admin cannot be zero");
        admin = _admin;
    }

    function initializeUser(address user, uint256 initialTrustScore) external onlyAdmin {
        require(user != address(0), "Invalid user");
        require(!isInitialized[user], "Already initialized");
        require(initialTrustScore <= uint256(type(int256).max), "Score too large");

        int256 initScore = int256(initialTrustScore);
        tokenBalance[user] = initScore;
        isInitialized[user] = true;

        emit UserInitialized(user, initScore);
    }

    function mint(address user, uint256 amount) external onlyAdmin {
        require(user != address(0), "Invalid user");
        require(amount > 0, "Amount must be > 0");
        require(amount <= uint256(type(int256).max), "Amount too large");

        int256 newBalance = tokenBalance[user] + int256(amount);
        tokenBalance[user] = newBalance;

        emit Minted(user, amount, newBalance);
    }

    function burn(address user, uint256 amount) external onlyAdmin {
        require(user != address(0), "Invalid user");
        require(amount > 0, "Amount must be > 0");
        require(amount <= uint256(type(int256).max), "Amount too large");

        int256 newBalance = tokenBalance[user] - int256(amount);
        tokenBalance[user] = newBalance;

        emit Burned(user, amount, newBalance);
    }

    // Optional: allow admin rotation if LoanManager is upgraded
    function setAdmin(address newAdmin) external onlyAdmin {
        require(newAdmin != address(0), "Invalid new admin");
        admin = newAdmin;
    }

    // No transfer or approval functions — soulbound by design
}