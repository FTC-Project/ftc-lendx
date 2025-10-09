// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/*
  Overview (for this PR):
  - Single controller of the loan lifecycle: Requested -> Funded -> Active -> Repaid/Defaulted.
  - Orchestrates calls to Escrow (hold/release/repay), LiquidityPool (if using pooled funds),
    and CreditTrustToken (mint a badge after successful repayment).

  What we’ll tighten in a follow-up PR (not blocking this one):
  - Enforce real value flows:
      * P2P: fundLoan should be payable and forward msg.value to Escrow.
      * Pool: pool should send ETH straight to Escrow.
  - Gate who can call which step (e.g., only borrower or only registry at the right times).
  - Compute the actual amount due (principal + interest) and handle due dates / default case.
  - Emit richer events (include amounts and whether funding came from Pool or P2P).
  - Mark referenced contract addresses as immutable and add a simple pause switch for emergencies.
*/



interface IEscrow {
    function lockFunds(uint256 loanId, address lender, uint256 amount) external;
    function releaseToBorrower(uint256 loanId, address borrower) external;
    function repay(uint256 loanId, uint256 amount) external;
}

interface ILiquidityPool {
    function fundLoan(uint256 loanId, uint256 amount) external returns (bool);
    function receiveRepayment(uint256 loanId, uint256 amount) external;
}

interface ICreditTrustToken {
    function mint(address borrower, uint256 score) external;
}

contract LoanRegistry {
    enum LoanStatus { Requested, Funded, Active, Repaid, Defaulted }

    struct Loan {
        address borrower;
        address lender;
        uint256 amount;
        uint256 interestRate;
        uint256 dueDate;
        LoanStatus status;
        bool isFromPool;
    }

    uint256 public nextLoanId;
    mapping(uint256 => Loan) public loans;

    IEscrow public escrow;
    ILiquidityPool public pool;
    ICreditTrustToken public creditToken;
    address public admin;

    event LoanRequested(uint256 loanId, address borrower, uint256 amount);
    event LoanFunded(uint256 loanId, address lender);
    event LoanRepaid(uint256 loanId);
    event LoanDefaulted(uint256 loanId);

    constructor(address _escrow, address _pool, address _creditToken) {
        admin = msg.sender;
        escrow = IEscrow(_escrow);
        pool = ILiquidityPool(_pool);
        creditToken = ICreditTrustToken(_creditToken);
    }

    // requestLoan: called by borrower to request a loan
    // includes: loan amount, loan duration, loan interest rate and P2P or pool funding
    function requestLoan(uint256 amount, uint256 interestRate, uint256 duration, bool fromPool) external {   
        /*
        1) borrower indicates loan terms
        2) contract creates a new loan record with this information, marking it as “requested”
        3) It saves this loan on the blockchain so it can be tracked
        4) It sends out a notification (event) so apps or bots can know a new loan was requested.
        */
        loans[nextLoanId] = Loan(msg.sender, address(0), amount, interestRate, block.timestamp + duration, LoanStatus.Requested, fromPool);
        emit LoanRequested(nextLoanId, msg.sender, amount);
        nextLoanId++; // Prepares a new ID for the next loan someone requests.
    }

    // fundLoan: called by a lender to fund a loan request
    // checks if the loan is P2P or pool-based, locks funds in escrow, and marks the loan as funded
    function fundLoan(uint256 loanId) external payable {
        /*
        1) Fetch the loan record using loanId.
        2) Check that the loan is still in the “Requested” state; otherwise it cannot be funded.
        3) Determine how the loan will be funded:
            - If the loan is from a liquidity pool:
                a) Call the pool contract to fund the loan.
                b) Ensure the pool has enough funds; fail if it cannot fund.
            - If the loan is P2P:
                a) Assign the lender to the loan record.
                b) Call the escrow contract to lock the lender’s funds until the borrower receives them.
        4) Update the loan’s status to “Funded”.
        5) Emit a LoanFunded event so off-chain apps or bots know the loan has been funded.
        */
        Loan storage loan = loans[loanId];
        require(loan.status == LoanStatus.Requested, "Not available");

        if (loan.isFromPool) {
            require(pool.fundLoan(loanId, loan.amount), "Pool funding failed");
        } else {
            loan.lender = msg.sender;
            escrow.lockFunds(loanId, msg.sender, loan.amount);
        }

        loan.status = LoanStatus.Funded;
        emit LoanFunded(loanId, msg.sender);
    }
    // activateLoan: called to release the funded loan to the borrower
    // changes the loan status from Funded to Active
    function activateLoan(uint256 loanId) external {
        Loan storage loan = loans[loanId];
        require(loan.status == LoanStatus.Funded, "Invalid state");
        // if loan status is funded, funds are released from escrow to borrower
        escrow.releaseToBorrower(loanId, loan.borrower);
        loan.status = LoanStatus.Active;
    }
    // markRepaid: called when a borrower repays a loan
    // handles repayment distribution and rewards borrower with a credit token
    function markRepaid(uint256 loanId, uint256 amount) external {
        /*
        1) Fetch the loan record using the loanId.
        2) Check that the loan is currently “Active”
        3) Call escrow to handle the repayment (sending funds to the lender or escrow logic).
        4) If the loan was funded from a liquidity pool, send the repayment back to the pool.
        5) Update the loan status to “Repaid”.
        6) Mint a non-transferable CreditTrustToken to reward the borrower for good repayment behaviour.
        7) Emit a LoanRepaid event so off-chain apps or bots are notified of successful repayment.
        */
        Loan storage loan = loans[loanId];
        require(loan.status == LoanStatus.Active, "Invalid state");
        escrow.repay(loanId, amount);

        if (loan.isFromPool) pool.receiveRepayment(loanId, amount);

        loan.status = LoanStatus.Repaid;
        creditToken.mint(loan.borrower, 1);
        emit LoanRepaid(loanId);
    }
}
