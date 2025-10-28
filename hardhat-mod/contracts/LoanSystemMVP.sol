// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
/**
 * @title CreditTrustToken interface
 * @notice Minimal interface to interact with the provided CreditTrustToken.sol
 */
interface ICreditTrustToken {
    function tokenBalance(address user) external view returns (int256);
    function isInitialized(address user) external view returns (bool);
    function initializeUser(address user, uint256 initialTrustScore) external;
    function mint(address user, uint256 amount) external;
    function burn(address user, uint256 amount) external;
}

/**
 * @title LoanSystemMVP
 * @notice Single-contract MVP that combines LoanManager, Escrow, and Liquidity Pool.
 *         - Lenders deposit ETH and receive pool shares
 *         - Admin funds loans from the pool, releases to borrowers, and settles repayments/defaults
 *         - Borrowers repay principal + interest; interest accrues to the pool
 *         - CreditTrustToken integrated: initialize borrower (if needed), mint on on-time repayment, burn on default
 */
contract LoanSystemMVP {
    // ------------------
    // Admin and external
    // ------------------
    address public admin;
    ICreditTrustToken public ctt;

    modifier onlyAdmin() {
        require(msg.sender == admin, "Unauthorized: not admin");
        _;
    }

    // ------------------
    // Liquidity (shares)
    // ------------------
    // Share accounting lets deposits and withdrawals track proportional interest.
    uint256 public totalPool;      // Total ETH in pool (including interest)
    uint256 public totalShares;    // Total shares issued
    mapping(address => uint256) public sharesOf; // user => shares

    // FTCToken
    IERC20 public FTCToken;

    // ------------------
    // Loan lifecycle
    // ------------------
    enum State {
        Created,
        Funded,
        Disbursed,
        Repaid,
        Defaulted
    }

    struct Loan {
        address payable borrower;
        uint256 principal;
        uint256 aprBps;    // interest rate in basis points annualized (e.g., 1200 = 12%)
        uint256 termDays;  // loan term in days
        State state;
        uint256 escrowBalance; // funds reserved for this loan before disbursement and while settling
        uint256 dueDate;       // set at disbursement time: block.timestamp + termDays * 1 days
    }

    uint256 public nextId;
    mapping(uint256 => Loan) public loans;

    // ------------------
    // Events
    // ------------------
    // Liquidity
    event Deposited(address indexed user, uint256 amount, uint256 mintedShares);
    event Withdrawn(address indexed user, uint256 amount, uint256 burnedShares);

    // Loans
    event LoanCreated(uint256 indexed id, address indexed borrower, uint256 principal, uint256 aprBps, uint256 termDays);
    event LoanFunded(uint256 indexed id, uint256 amount);
    event LoanDisbursed(uint256 indexed id, address indexed borrower, uint256 amount, uint256 dueDate);
    event LoanRepaid(uint256 indexed id, address indexed borrower, uint256 principal, uint256 interest, bool onTime);
    event LoanDefaulted(uint256 indexed id, address indexed borrower, uint256 principal);

    // ------------------
    // Constructor
    // ------------------
    constructor(address _admin, address _ctt, address _FTCToken) {
        require(_admin != address(0), "Invalid admin");
        require(_ctt != address(0), "Invalid CTT");
        require(_FTCToken != address(0), "Invalid FTCToken");
        admin = _admin;
        ctt = ICreditTrustToken(_ctt);
        FTCToken = IERC20(_FTCToken);
        nextId = 1;
    }

    // ------------------
    // Liquidity functions
    // ------------------

    /**
     * @notice Deposit ETH to the pool and receive proportional shares.
     */
    function deposit() external payable {
        require(msg.value > 0, "Deposit must be > 0");

        uint256 mintedShares;
        if (totalShares == 0 || totalPool == 0) {
            // First deposit initializes shares 1:1 with amount
            mintedShares = msg.value;
        } else {
            // Mint shares proportional to current pool value
            mintedShares = (msg.value * totalShares) / totalPool;
        }

        totalPool += msg.value;
        totalShares += mintedShares;
        sharesOf[msg.sender] += mintedShares;

        emit Deposited(msg.sender, msg.value, mintedShares);
    }

    // ERC20 version of deposit
    /// @notice Deposit FTCT tokens to the pool and receive proportional shares.
    function depositFTCT(uint256 amount) external {
        require(amount > 0, "Deposit must be > 0");

        // Pull tokens from the user into this contract
        bool ok = FTCToken.transferFrom(msg.sender, address(this), amount);
        require(ok, "FTCT transfer failed");

        uint256 mintedShares;
        if (totalShares == 0 || totalPool == 0) {
            // First deposit initializes shares 1:1 with amount
            mintedShares = amount;
        } else {
            // Mint shares proportional to current pool value
            mintedShares = (amount * totalShares) / totalPool;
        }

        totalPool += amount;
        totalShares += mintedShares;
        sharesOf[msg.sender] += mintedShares;

        emit Deposited(msg.sender, amount, mintedShares);
    }

    /**
     * @notice Withdraw ETH by redeeming shares. Amount is proportional to pool value.
     * @param shareAmount Number of shares to redeem.
     */
    function withdraw(uint256 shareAmount) external {
        require(shareAmount > 0, "shareAmount must be > 0");
        require(sharesOf[msg.sender] >= shareAmount, "Insufficient shares");
        require(totalShares > 0, "No shares");

        // User receives amount = shareAmount / totalShares * totalPool
        uint256 amount = (shareAmount * totalPool) / totalShares;

        // Update accounting
        sharesOf[msg.sender] -= shareAmount;
        totalShares -= shareAmount;
        totalPool -= amount;

        // Transfer
        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        require(ok, "Withdraw transfer failed");

        emit Withdrawn(msg.sender, amount, shareAmount);
    }

    // ERC20 version of withdraw
    function withdrawFTCT(uint256 shareAmount) external {
        require(shareAmount > 0, "shareAmount must be > 0");
        require(sharesOf[msg.sender] >= shareAmount, "Insufficient shares");
        require(totalShares > 0, "No shares");

        // User receives amount = shareAmount / totalShares * totalPool
        uint256 amount = (shareAmount * totalPool) / totalShares;

        // Update accounting
        sharesOf[msg.sender] -= shareAmount;
        totalShares -= shareAmount;
        totalPool -= amount;

        // Transfer
        require(FTCToken.transfer(msg.sender, amount), "Token transfer failed");

        emit Withdrawn(msg.sender, amount, shareAmount);
    }

    /**
     * @notice Accept direct top-ups to the pool (treated as donations that increase pool without minting shares).
     */
    receive() external payable {
        totalPool += msg.value;
        // No event for simplicity; donors don't receive shares.
    }

    // ------------------
    // Loan functions
    // ------------------

    /**
     * @notice Create a loan entry. Optionally initializes the borrower's CreditTrustToken profile at zero.
     * @dev Returns the loan id.
     */
    function createLoan(address payable borrower, uint256 amount, uint256 aprBps, uint256 termDays)
        external
        onlyAdmin
        returns (uint256 id)
    {
        require(borrower != address(0), "Invalid borrower");
        require(amount > 0, "Amount must be > 0");
        require(aprBps > 0, "aprBps must be > 0");
        require(termDays > 0, "termDays must be > 0");

        id = nextId++;
        loans[id] = Loan({
            borrower: borrower,
            principal: amount,
            aprBps: aprBps,
            termDays: termDays,
            state: State.Created,
            escrowBalance: 0,
            dueDate: 0
        });

        // Initialize borrower in CTT if not already
        if (!ctt.isInitialized(borrower)) {
            ctt.initializeUser(borrower, 0);
        }

        emit LoanCreated(id, borrower, amount, aprBps, termDays);
    }

    /**
     * @notice Move pool funds to loan escrow reserve. Only admin.
     * @dev Ensures pool has sufficient free liquidity.
     */
    function markFunded(uint256 id) external onlyAdmin {
        Loan storage ln = loans[id];
        require(ln.state == State.Created, "Invalid state");
        require(totalPool >= ln.principal, "Insufficient pool");

        // Reserve funds for loan in escrow
        ln.escrowBalance += ln.principal;
        totalPool -= ln.principal; // funds reserved out of pool

        ln.state = State.Funded;
        emit LoanFunded(id, ln.principal);
    }

    /**
     * @notice Release escrowed funds to borrower. Sets due date and moves state to Disbursed. Only admin.
     */
    function markDisbursed(uint256 id) external onlyAdmin {
        Loan storage ln = loans[id];
        require(ln.state == State.Funded, "Invalid state");
        require(ln.escrowBalance == ln.principal, "Escrow mismatch");

        ln.state = State.Disbursed;
        ln.dueDate = block.timestamp + (ln.termDays * 1 days);

        // Transfer principal to borrower
        uint256 amount = ln.principal;
        ln.escrowBalance = 0;

        (bool ok, ) = ln.borrower.call{value: amount}("");
        require(ok, "Borrower transfer failed");

        emit LoanDisbursed(id, ln.borrower, amount, ln.dueDate);
    }


    // ERC20 version of disburse
    function markDisbursedFTCT(uint256 id) external onlyAdmin {
        Loan storage ln = loans[id];
        require(ln.state == State.Funded, "Invalid state");
        require(ln.escrowBalance == ln.principal, "Escrow mismatch");

        ln.state = State.Disbursed;
        ln.dueDate = block.timestamp + (ln.termDays * 1 days);

        // Transfer principal to borrower
        uint256 amount = ln.principal;
        ln.escrowBalance = 0;

        require(FTCToken.transfer(ln.borrower, amount), "Token transfer failed");

        emit LoanDisbursed(id, ln.borrower, amount, ln.dueDate);
    }

    /**
     * @notice Borrower repays the loan by sending principal + interest. Anyone can call, msg.value must cover due amount.
     * @param id Loan id.
     * @param onTime Whether this repayment counts as on-time for reputation purposes.
     *               You can pass `onTime = (block.timestamp <= dueDate)` off-chain if desired.
     */
    function markRepaid(uint256 id, bool onTime) external payable {
        Loan storage ln = loans[id];
        require(ln.state == State.Disbursed, "Invalid state");

        // Calculate simple interest: principal * aprBps * termDays / (10000 * 365)
        uint256 interest = _calcInterest(ln.principal, ln.aprBps, ln.termDays);
        uint256 totalDue = ln.principal + interest;
        require(msg.value >= totalDue, "Insufficient repayment");

        ln.state = State.Repaid;

        // Settlement: interest goes to pool, principal closes loan.
        // Here, we add interest to pool (benefits all lenders via share pricing).
        totalPool += totalDue;

        // Excess repayment (if any) returned to sender
        uint256 excess = msg.value - totalDue;
        if (excess > 0) {
            (bool refundOk, ) = payable(msg.sender).call{value: excess}("");
            require(refundOk, "Excess refund failed");
        }

        // Reputation update via CreditTrustToken
        // MVP rule: mint principal amount on on-time repayment; mint half if late.
        uint256 trustMint = onTime ? ln.principal : (ln.principal / 2);
        if (trustMint > 0) {
            ctt.mint(ln.borrower, trustMint);
        }

        emit LoanRepaid(id, ln.borrower, ln.principal, interest, onTime);
    }
    // ERC20 version of repay
    function markRepaidFTCT(uint256 id, bool onTime, uint256 amount) external {
        Loan storage ln = loans[id];
        require(ln.state == State.Disbursed, "Invalid state");

        uint256 interest = _calcInterest(ln.principal, ln.aprBps, ln.termDays);
        uint256 totalDue = ln.principal + interest;
        require(amount >= totalDue, "Insufficient repayment");

        // Transfer tokens from borrower
        require(FTCToken.transferFrom(msg.sender, address(this), totalDue), "Repayment transfer failed");

        ln.state = State.Repaid;
        totalPool += totalDue;

        uint256 trustMint = onTime ? ln.principal : (ln.principal / 2);
        if (trustMint > 0) ctt.mint(ln.borrower, trustMint);

        emit LoanRepaid(id, ln.borrower, ln.principal, interest, onTime);
    }

    /**
     * @notice Declare loan default. Only admin.
     * @dev No further transfers; reputation penalty applied. Any residual escrowBalance (should be zero post-disbursement).
     */
    function markDefaulted(uint256 id) external onlyAdmin {
        Loan storage ln = loans[id];
        require(ln.state == State.Disbursed, "Invalid state");

        ln.state = State.Defaulted;

        // Reputation penalty via CreditTrustToken
        // MVP rule: burn principal amount on default.
        ctt.burn(ln.borrower, ln.principal);

        emit LoanDefaulted(id, ln.borrower, ln.principal);
    }

    // ------------------
    // Internal helpers
    // ------------------

    function _calcInterest(uint256 principal, uint256 aprBps, uint256 termDays) public pure returns (uint256) {
        // Simple interest (non-compounding): principal * aprBps * termDays / (10000 * 365)
        // Note: Uses integer division; acceptable for MVP.
        return (principal * aprBps * termDays) / (10000 * 365);
    }

    // ------------------
    // Admin utilities
    // ------------------

    /**
     * @notice Rotate admin. Only admin.
     */
    function setAdmin(address newAdmin) external onlyAdmin {
        require(newAdmin != address(0), "Invalid admin");
        admin = newAdmin;
    }
}