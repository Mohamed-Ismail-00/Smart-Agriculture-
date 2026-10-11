"""
app/security/encryption.py
--------------------------
Provides symmetric encryption utilities for sensitive data at rest (e.g. API keys)
using Fernet (AES128 in CBC mode with a SHA256 HMAC authentication).
"""

from cryptography.fernet import Fernet
from app.core.config import settings

_fernet = None

def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return _fernet

def encrypt_string(plaintext: str) -> str:
    """Encrypt a string and return a base64-encoded URL-safe string."""
    if not plaintext:
        return plaintext
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()

def decrypt_string(ciphertext: str) -> str:
    """Decrypt a base64-encoded URL-safe string."""
    if not ciphertext:
        return ciphertext
    try:
        fernet = _get_fernet()
        return fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        # If decryption fails (e.g., key rotated or not encrypted), return as-is
        # to support legacy unencrypted data transparently.
        return ciphertext
