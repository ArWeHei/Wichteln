import hashlib
import secrets


def new_token():
    """Zufälliges URL-sicheres Token mit 128 Bit."""
    return secrets.token_urlsafe(16)


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()
