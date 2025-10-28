import os

from eth_account import Account

from cryptography.fernet import Fernet
from django.conf import settings

_key = settings.FERNET_KEY.encode()
fernet = Fernet(_key)


def encrypt_secret(secret: str) -> bytes:
    return fernet.encrypt(secret.encode())


def decrypt_secret(blob: bytes) -> str:
    return fernet.decrypt(bytes(blob)).decode()




RPC_URL = settings.WEB3_PROVIDER_URL 

def create_new_user_wallet() -> tuple[str, str]:
    """
    Creates a new Ethereum-compatible wallet (keypair).
    This process is purely cryptographic and runs locally.
    """
    # 1. Generate a new, random wallet/account
    new_account = Account.create()

    # 2. Extract key data
    private_key = new_account.key.hex()
    evm_address = new_account.address
    return private_key, evm_address