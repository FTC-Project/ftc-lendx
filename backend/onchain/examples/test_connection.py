"""
Test Web3 Connection and Services

Run this script to verify your Web3 integration is working correctly.

Usage:
    python backend/onchain/examples/test_connection.py
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from backend.apps.tokens.services import (
    FTCTokenService,
    LoanSystemService,
    CreditTrustTokenService,
)
from django.conf import settings


def test_connection():
    """Test Web3 connection"""
    print("=" * 60)
    print("Testing Web3 Connection")
    print("=" * 60)
    
    try:
        ftc = FTCTokenService()
        print(f"✅ Web3 connected")
        print(f"   Provider: {ftc.web3.provider.endpoint_uri}")
        print(f"   Connected: {ftc.web3.is_connected()}")
        print(f"   Chain ID: {ftc.web3.eth.chain_id}")
        print(f"   Block number: {ftc.get_block_number()}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_ftc_token():
    """Test FTCToken service"""
    print("\n" + "=" * 60)
    print("Testing FTCToken Service")
    print("=" * 60)
    
    try:
        ftc = FTCTokenService()
        
        print(f"✅ FTCToken service initialized")
        print(f"   Contract address: {ftc.contract_address}")
        
        # Get token info
        info = ftc.get_token_info()
        print(f"   Name: {info['name']}")
        print(f"   Symbol: {info['symbol']}")
        print(f"   Decimals: {info['decimals']}")
        
        # Get owner
        owner = ftc.get_owner()
        print(f"   Owner: {owner}")
        
        # Get total supply
        supply = ftc.get_total_supply()
        print(f"   Total supply: {supply}")
        
        # Get admin balance
        if settings.ADMIN_ADDRESS:
            balance = ftc.get_balance(settings.ADMIN_ADDRESS)
            print(f"   Admin balance: {balance} FTCT")
        
        return True
    except Exception as e:
        print(f"❌ FTCToken test failed: {e}")
        return False


def test_loan_system():
    """Test LoanSystem service"""
    print("\n" + "=" * 60)
    print("Testing LoanSystem Service")
    print("=" * 60)
    
    try:
        loan = LoanSystemService()
        
        print(f"✅ LoanSystem service initialized")
        print(f"   Contract address: {loan.contract_address}")
        
        # Get admin
        admin = loan.get_admin()
        print(f"   Admin: {admin}")
        
        # Get pool info
        total_pool = loan.get_total_pool()
        total_shares = loan.get_total_shares()
        next_loan_id = loan.get_next_loan_id()
        
        print(f"   Total pool: {total_pool} FTCT")
        print(f"   Total shares: {total_shares}")
        print(f"   Next loan ID: {next_loan_id}")
        
        return True
    except Exception as e:
        print(f"❌ LoanSystem test failed: {e}")
        return False


def test_credit_trust():
    """Test CreditTrustToken service"""
    print("\n" + "=" * 60)
    print("Testing CreditTrustToken Service")
    print("=" * 60)
    
    try:
        ctt = CreditTrustTokenService()
        
        print(f"✅ CreditTrustToken service initialized")
        print(f"   Contract address: {ctt.contract_address}")
        
        # Get admin and loan system
        admin = ctt.get_admin()
        loan_system = ctt.get_loan_system()
        
        print(f"   Admin: {admin}")
        print(f"   Loan system: {loan_system}")
        
        # Check admin balance
        if settings.ADMIN_ADDRESS:
            balance = ctt.get_balance(settings.ADMIN_ADDRESS)
            initialized = ctt.is_initialized(settings.ADMIN_ADDRESS)
            print(f"   Admin CTT balance: {balance}")
            print(f"   Admin initialized: {initialized}")
        
        return True
    except Exception as e:
        print(f"❌ CreditTrustToken test failed: {e}")
        return False


def test_settings():
    """Test Django settings configuration"""
    print("\n" + "=" * 60)
    print("Testing Django Settings")
    print("=" * 60)
    
    settings_ok = True
    
    # Check Web3 provider
    if hasattr(settings, 'WEB3_PROVIDER_URL'):
        print(f"✅ WEB3_PROVIDER_URL: {settings.WEB3_PROVIDER_URL}")
    else:
        print("❌ WEB3_PROVIDER_URL not set")
        settings_ok = False
    
    # Check admin address
    if hasattr(settings, 'ADMIN_ADDRESS') and settings.ADMIN_ADDRESS:
        print(f"✅ ADMIN_ADDRESS: {settings.ADMIN_ADDRESS}")
    else:
        print("❌ ADMIN_ADDRESS not set")
        settings_ok = False
    
    # Check contract addresses
    for name in ['FTCTOKEN_ADDRESS', 'CREDITTRUST_ADDRESS', 'LOANSYSTEM_ADDRESS']:
        if hasattr(settings, name) and getattr(settings, name):
            print(f"✅ {name}: {getattr(settings, name)}")
        else:
            print(f"❌ {name} not set")
            settings_ok = False
    
    # Check ABI paths
    for name in ['FTCTOKEN_ABI_PATH', 'CREDITTRUST_ABI_PATH', 'LOANSYSTEM_ABI_PATH']:
        if hasattr(settings, name):
            path = getattr(settings, name)
            if path.exists():
                print(f"✅ {name}: {path}")
            else:
                print(f"⚠️  {name} path does not exist: {path}")
                print(f"   Run: cd hardhat-mod && node scripts/export-abis.js")
                settings_ok = False
        else:
            print(f"❌ {name} not set")
            settings_ok = False
    
    return settings_ok


def main():
    """Run all tests"""
    print("\n" + "🧪 Web3 Integration Test Suite" + "\n")
    
    results = {
        'Settings': test_settings(),
        'Connection': test_connection(),
        'FTCToken': test_ftc_token(),
        'LoanSystem': test_loan_system(),
        'CreditTrust': test_credit_trust(),
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your Web3 integration is ready!")
        print("\n📚 Next steps:")
        print("   1. Review examples: backend/onchain/examples/complete_workflow.py")
        print("   2. Read guides: backend/onchain/WEB3_USAGE_GUIDE.md")
        print("   3. Start building!")
    else:
        print("\n⚠️  Some tests failed. Please check:")
        print("   1. Is Hardhat node running? (npx hardhat node)")
        print("   2. Are contracts deployed?")
        print("   3. Have you exported ABIs? (node scripts/export-abis.js)")
        print("   4. Is .env file configured correctly?")
    
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

