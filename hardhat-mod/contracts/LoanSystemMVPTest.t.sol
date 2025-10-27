// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "./LoanSystemMVP.sol";
import "./CreditTrustToken.sol";
import "./FTCToken.sol";

contract LoanSystemMVPTest is Test {
    LoanSystemMVP loanSystem;
    CreditTrustToken ctt;
    FTCToken ftcToken;

    address admin = address(0xA11CE);
    address lender = address(0xBEEF);
    address borrower = address(0xCAFE);

    function setUp() public {
        // Deploy CreditTrustToken with admin
        vm.prank(admin);
        ctt = new CreditTrustToken(admin);

        // Deploy LoanSystemMVP
        vm.prank(admin);
        loanSystem = new LoanSystemMVP(admin, address(ctt), address(ftcToken));

        // Rotate admin of CTT to LoanSystem
        vm.prank(admin);
        ctt.setAdmin(address(loanSystem));

        // Fund lender with ETH
        vm.deal(lender, 100 ether);
        vm.deal(borrower, 10 ether);
    }

    function testDepositAndWithdraw() public {
        vm.startPrank(lender);
        loanSystem.deposit{value: 10 ether}();
        assertEq(loanSystem.totalPool(), 10 ether);

        uint256 shares = loanSystem.sharesOf(lender);
        assertGt(shares, 0);

        loanSystem.withdraw(shares / 2);
        vm.stopPrank();

        // After withdrawing half, pool should be ~5 ether
        assertApproxEqAbs(loanSystem.totalPool(), 5 ether, 1e14);
    }

    function testLoanLifecycleRepayOnTime() public {
        // Lender deposits
        vm.prank(lender);
        loanSystem.deposit{value: 20 ether}();

        // Admin creates loan
        vm.prank(admin);
        uint256 loanId = loanSystem.createLoan(payable(borrower), 5 ether, 1200, 30);

        // Fund loan
        vm.prank(admin);
        loanSystem.markFunded(loanId);

        // Disburse loan
        uint256 balBefore = borrower.balance;
        vm.prank(admin);
        loanSystem.markDisbursed(loanId);
        assertGt(borrower.balance, balBefore);

        // Calculate repayment
        uint256 interest = loanSystem._calcInterest(5 ether, 1200, 30);
        uint256 totalDue = 5 ether + interest;

        // Borrower repays
        vm.prank(borrower);
        loanSystem.markRepaid{value: totalDue}(loanId, true);

        // Loan state should be Repaid
        (,,,, LoanSystemMVP.State state,,) = loanSystem.loans(loanId);
        assertEq(uint(state), uint(LoanSystemMVP.State.Repaid));

        // Reputation should be positive
        int256 trustBal = ctt.tokenBalance(borrower);
        assertGt(trustBal, 0);
    }

    function testLoanDefault() public {
        // Lender deposits
        vm.prank(lender);
        loanSystem.deposit{value: 20 ether}();

        // Create loan
        vm.prank(admin);
        uint256 loanId = loanSystem.createLoan(payable(borrower), 5 ether, 1200, 30);

        // Fund + Disburse
        vm.startPrank(admin);
        loanSystem.markFunded(loanId);
        loanSystem.markDisbursed(loanId);
        vm.stopPrank();

        // Default loan
        vm.prank(admin);
        loanSystem.markDefaulted(loanId);

        // Loan state should be Defaulted
        (,,,, LoanSystemMVP.State state,,) = loanSystem.loans(loanId);
        assertEq(uint(state), uint(LoanSystemMVP.State.Defaulted));

        // Reputation should be negative
        int256 trustBal = ctt.tokenBalance(borrower);
        assertLt(trustBal, 0);
    }
}