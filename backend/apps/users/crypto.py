import os
# from dotenv import load_dotenv
# load_dotenv()
from cryptography.fernet import Fernet

_key = os.environ["FERNET_KEY"].encode()
fernet = Fernet(_key)

def encrypt_secret(secret: str) -> bytes:
    return fernet.encrypt(secret.encode())

def decrypt_secret(blob: bytes) -> str:
    return fernet.decrypt(blob).decode()
