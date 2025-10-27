// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../contracts/CreditTrustToken.sol";

contract CreditTrustTokenTest is Test {
    CreditTrustToken token;
    address admin = address(0xABCD);
    address user1 = address(0x1111);
    address user2 = address(0x2222);

    function setUp() public {
        vm.prank(admin);
        token = new CreditTrustToken(admin);
    }

    function test_AdminIsSet() public view {
        require(token.admin() == admin, "Admin should be set correctly");
    }

    function test_InitializeUser() public {
        vm.prank(admin);
        token.initializeUser(user1, 10);
        assertEq(token.tokenBalance(user1), 10);
        assertTrue(token.isInitialized(user1));
    }

    function test_DoubleInitialize_Reverts() public {
    vm.startPrank(admin);
    token.initializeUser(user1, 5);
    vm.expectRevert("Already initialized");
    token.initializeUser(user1, 7);
    }


    function test_MintIncreasesBalance() public {
        vm.startPrank(admin);
        token.initializeUser(user1, 0);
        token.mint(user1, 20);
        assertEq(token.tokenBalance(user1), 20);
    }

    function test_BurnDecreasesBalance() public {
        vm.startPrank(admin);
        token.initializeUser(user1, 50);
        token.burn(user1, 30);
        assertEq(token.tokenBalance(user1), 20);
    }

    function test_BurnCanGoNegative() public {
        vm.startPrank(admin);
        token.initializeUser(user1, 10);
        token.burn(user1, 50);
        assertEq(token.tokenBalance(user1), -40);
    }

    function test_NonAdminMint_Reverts() public {
    vm.prank(user2);
    vm.expectRevert("Unauthorized: not admin or loan system");
    token.mint(user1, 10);
    }


    function test_AdminRotation() public {
        address newAdmin = address(0x9999);
        vm.prank(admin);
        token.setAdmin(newAdmin);
        assertEq(token.admin(), newAdmin);
    }

    function test_NonAdminSetAdmin_Reverts() public {
    vm.prank(user1);
    vm.expectRevert("Unauthorized: not admin or loan system");
    token.setAdmin(user2);
    }

    function test_GetBalanceAfterMintAndBurn() public {
    vm.startPrank(admin);

    // Initialize user with score 10
    token.initializeUser(user1, 10);
    assertEq(token.tokenBalance(user1), 10);

    // Mint 20 more
    token.mint(user1, 20);
    assertEq(token.tokenBalance(user1), 30);

    // Burn 50 (goes negative)
    token.burn(user1, 50);
    assertEq(token.tokenBalance(user1), -20);
    }

}