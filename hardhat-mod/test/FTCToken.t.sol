// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../contracts/FTCToken.sol";

contract FTCTokenTest is Test {
    FTCToken token;
    address admin = address(0xABCD);
    address user1 = address(0x1111);
    address user2 = address(0x2222);

    function setUp() public {
        vm.prank(admin);
        token = new FTCToken(admin);
    }

    function test_AdminIsOwner() public view {
        assertEq(token.owner(), admin, "Owner should be set to admin");
    }

    function test_InitialSupplyMintedToAdmin() public view {
        uint256 expected = 1_000_000 * 10 ** token.decimals();
        assertEq(token.balanceOf(admin), expected, "Admin should have initial supply");
    }

    function test_AdminCanMint() public {
        vm.prank(admin);
        token.mint(user1, 100 ether);
        assertEq(token.balanceOf(user1), 100 ether);
    }

    function test_NonAdminMintReverts() public {
        vm.prank(user1);
        vm.expectRevert(
            abi.encodeWithSelector(
                Ownable.OwnableUnauthorizedAccount.selector,
                user1
            )
        );
        token.mint(user1, 50 ether);
    }

    function test_TransferBetweenUsers() public {
        // Mint to user1
        vm.prank(admin);
        token.mint(user1, 200 ether);

        // Transfer to user2
        vm.prank(user1);
        token.transfer(user2, 75 ether);

        assertEq(token.balanceOf(user1), 125 ether);
        assertEq(token.balanceOf(user2), 75 ether);
    }

    function test_ApproveAndTransferFrom() public {
        // Mint to user1
        vm.prank(admin);
        token.mint(user1, 150 ether);

        // user1 approves user2
        vm.prank(user1);
        token.approve(user2, 100 ether);

        // user2 transfers on behalf of user1
        vm.prank(user2);
        token.transferFrom(user1, user2, 60 ether);

        assertEq(token.balanceOf(user1), 90 ether);
        assertEq(token.balanceOf(user2), 60 ether);
        assertEq(token.allowance(user1, user2), 40 ether);
    }

    function test_TransferFailsIfInsufficientBalance() public {
        vm.prank(admin);
        token.mint(user1, 10 ether);

        vm.prank(user1);
        vm.expectRevert(); // ERC20: transfer amount exceeds balance
        token.transfer(user2, 20 ether);
    }

    function test_AdminRotation() public {
        address newAdmin = address(0x9999);
        vm.prank(admin);
        token.transferOwnership(newAdmin);
        assertEq(token.owner(), newAdmin);
    }

    function test_NonAdminTransferOwnershipReverts() public {
        vm.prank(user1);
        vm.expectRevert(
            abi.encodeWithSelector(
                Ownable.OwnableUnauthorizedAccount.selector,
                user1
            )
        );
        token.transferOwnership(user2);
    }
}