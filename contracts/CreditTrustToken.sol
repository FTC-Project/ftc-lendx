pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";

contract CreditTrustToken is ERC721URIStorage {
    address public loanRegistry;
    uint256 public nextTokenId;

    modifier onlyRegistry() {
        require(msg.sender == loanRegistry, "Unauthorized");
        _;
    }

    constructor(address _registry) ERC721("CreditTrustToken", "CTT") {
        loanRegistry = _registry;
    }

    function mint(address borrower, uint256 score) external onlyRegistry {
        uint256 tokenId = nextTokenId++;
        _safeMint(borrower, tokenId);
        _setTokenURI(tokenId, "ipfs://credit-data"); // placeholder
    }

    function _beforeTokenTransfer(address from, address to, uint256 tokenId, uint256 batchSize)
        internal
        override
    {
        require(from == address(0), "Non-transferable");
        super._beforeTokenTransfer(from, to, tokenId, batchSize);
    }
}
