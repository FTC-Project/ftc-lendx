// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title FTCToken - Example ERC20 token for lending/borrowing
/// @notice Owner can mint tokens to any address
contract FTCToken is ERC20, Ownable {
    constructor(address admin) ERC20("FTCToken", "FTCT") Ownable(admin) {
        // Optionally mint some initial supply to the deployer
        _mint(admin, 1_000_000 * 10 ** decimals());
    }

    /// @notice Mint new tokens to a specified address
    /// @param to The wallet address to receive tokens
    /// @param amount The number of tokens to mint (in wei units, e.g. 1e18 = 1 token)
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}