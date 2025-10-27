import os


from cryptography.fernet import Fernet
from django.conf import settings

_key = settings.FERNET_KEY.encode()
fernet = Fernet(_key)


def encrypt_secret(secret: str) -> bytes:
    return fernet.encrypt(secret.encode())


def decrypt_secret(blob: bytes) -> str:
    return fernet.decrypt(bytes(blob)).decode()
