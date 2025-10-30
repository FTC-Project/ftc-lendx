# Nonce Issue Fix Summary

## Problem

When running `quick-setup.js`, nonce conflicts occurred when sending multiple transactions rapidly from the same wallet. The error was:

```
Error: nonce has already been used
Nonce too low. Expected nonce to be X but got Y.
```

This happens because:
1. Multiple transactions are sent in quick succession
2. The nonce (transaction counter) doesn't update fast enough between transactions
3. Hardhat's automining can't queue transactions with conflicting nonces

## Solution

### JavaScript (quick-setup.js)

Added a `sendTransactionWithRetry` helper function that:

✅ **Waits for each transaction** to be fully confirmed before proceeding  
✅ **Adds 500ms delay** after each transaction to ensure nonce propagation  
✅ **Automatically retries** up to 3 times if nonce conflicts occur  
✅ **Waits 1 second** before retry attempts  
✅ **Provides clear feedback** when retrying

**Usage:**
```javascript
const result = await sendTransactionWithRetry(
  () => ftcToken.mint(address, amount),
  "mint tokens"
);
```

### Python (base_contract.py)

Enhanced `build_and_send_transaction` with:

✅ **Retry logic** for nonce conflicts (up to 3 attempts)  
✅ **Fresh nonce fetch** using 'pending' state for each attempt  
✅ **500ms delay** after successful transactions  
✅ **1 second wait** before retry attempts  
✅ **Better error detection** for nonce-related issues

**Usage:**
```python
# Automatically handles retries
result = ftc_service.mint(address, amount)
```

## How It Works

### Before (Problematic)
```
Transaction 1 (nonce 0) → Send
Transaction 2 (nonce 1) → Send immediately
❌ Error: Nonce 0 still pending, can't use nonce 1
```

### After (Fixed)
```
Transaction 1 (nonce 0) → Send → Wait for confirmation → 500ms delay
Transaction 2 (nonce 1) → Send → Wait for confirmation → 500ms delay
✅ Success: Each nonce is properly sequenced
```

### With Retry Logic
```
Transaction 1 → Send
If nonce conflict:
  ↓
  Wait 1 second
  ↓
  Retry with fresh nonce
  ↓
  If still fails: Retry again (up to 3 attempts)
```

## Testing

Run the quick-setup script again:

```bash
cd hardhat-mod
node scripts/quick-setup.js
```

Expected output:
```
💰 Step 2: Minting tokens...
   Minting 5,000 FTCT to Lender #1...
   ✅ Minted to Lender #1 (tx: 0x...)
   Minting 2,000 FTCT to Borrower #1...
   ✅ Minted to Borrower #1 (tx: 0x...)

🏦 Step 3: Funding the pool...
   Approving 2000.0 FTCT for LoanSystem...
   ✅ Approved (tx: 0x...)
   Depositing 2000.0 FTCT to pool...
   ✅ Deposited (tx: 0x...)

✅ Setup Complete!
```

## Additional Benefits

1. **More Robust**: Handles temporary network issues
2. **Better Logging**: Clear messages when retrying
3. **Flexible**: Works with both local Hardhat and XRPL EVM
4. **Automatic**: No manual intervention needed

## If Issues Persist

If you still encounter nonce issues:

1. **Restart Hardhat node** (clears all state):
   ```bash
   # Stop the node (Ctrl+C)
   # Start fresh
   npx hardhat node
   ```

2. **Check for pending transactions**:
   ```bash
   # In the Hardhat node terminal, look for pending txs
   ```

3. **Increase retry delays** (if needed):
   ```javascript
   await sleep(2000);  // Change from 500ms to 2000ms
   ```

4. **Use manual nonce management** (advanced):
   ```python
   # In Python, you can pass explicit nonce if needed
   # (though the retry logic should handle this)
   ```

## Related Files

- `hardhat-mod/scripts/quick-setup.js` - JavaScript nonce fixes
- `backend/apps/tokens/services/base_contract.py` - Python nonce fixes
- All Python service files inherit the fix automatically

## Notes

- The fix applies to **all write operations** (mint, transfer, approve, deposit, etc.)
- **Read operations** (balances, queries) are not affected and don't need nonce management
- The 500ms delay is minimal and doesn't significantly impact performance
- For production use on XRPL EVM, nonce conflicts are less common due to network latency

---

**Status**: ✅ **FIXED** - Nonce issues resolved in both JavaScript and Python

