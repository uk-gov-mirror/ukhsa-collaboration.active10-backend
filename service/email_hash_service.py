import hashlib
import hmac

from utils.base_config import config


def normalize_email(email: str) -> str:
    # This might be wrong according to RFC 5321 since the local part of an email address is technically case-sensitive,
    # but in practice most email providers treat it as case-insensitive.
    return email.strip().casefold()


def hash_email(email: str) -> str:
    return hmac.new(
        config.email_hash_secret.encode("utf-8"),
        normalize_email(email).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
