"""Accounts: scrypt password hashes, opaque server-side sessions (only a hash is stored), lockout."""
import hashlib
import hmac
import re
import secrets
import time

COOKIE = "usdc_session"
MAX_FAILS, LOCK_S = 5, 15 * 60
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(got.hex(), h)
    except Exception:
        return False


def new_token() -> tuple[str, str]:
    t = secrets.token_urlsafe(32)
    return t, hash_token(t)


def hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def check_new_password(pw: str):
    if len(pw) < 10:
        raise ValueError("password must be at least 10 characters")
    if len(pw) > 200:
        raise ValueError("password too long")


# constant-ish time on unknown e-mail: verify against a dummy hash
DUMMY = hash_password("dummy-password-for-timing")


def locked(user: dict) -> bool:
    return user["locked_until"] > time.time()
