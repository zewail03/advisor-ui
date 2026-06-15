"""Server-generated login OTP (one-time passcode).

Unlike TOTP, the SERVER mints the code, so there is no dependency on the client's
clock — which matters here because the demo machine runs on a 2026 date while a
phone authenticator would be on real time. The code is hashed at rest, single-use,
and expires after a few minutes. Delivery is pluggable: in this demo it's shown
on screen; in production you'd email/SMS it instead.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

OTP_TTL_MINUTES = 5


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def set_otp(student, code: str) -> None:
    """Store a freshly issued code (hashed) with an expiry on the student row."""
    student.otp_hash = _hash(code)
    student.otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)


def verify_and_consume(student, code: str) -> bool:
    """True if the code matches and is unexpired; clears it either way on success."""
    if not student.otp_hash or not student.otp_expires_at:
        return False
    if datetime.utcnow() > student.otp_expires_at:
        return False
    ok = secrets.compare_digest(student.otp_hash, _hash(code or ""))
    if ok:
        student.otp_hash = None
        student.otp_expires_at = None
    return ok
