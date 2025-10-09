pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
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
