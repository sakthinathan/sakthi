"""Security utility functions for password hashing, token generation, rate limiting, and revocation."""
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Set
from fastapi import HTTPException, status
from app.config import get_settings

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 100_000

# Fast in-memory token revocation cache (backed by database)
_revoked_signatures_cache: Set[str] = set()

# In-memory sliding-window rate limiter for failed login attempts
_login_failures: Dict[str, List[float]] = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes


def _get_signing_key() -> bytes:
    """Returns the dedicated token signing key, separate from external API keys."""
    settings = get_settings()
    return settings.token_signing_secret.encode("utf-8")


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a random 16-byte salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS,
    )
    return f"{ALGORITHM}${ITERATIONS}${salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored PBKDF2 hash using timing-safe comparison."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4:
            return False
        algo, iter_str, salt, stored_hash = parts
        if algo != ALGORITHM:
            return False
        iterations = int(iter_str)
        computed_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(computed_key.hex(), stored_hash)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed URL-safe token with JTI, expiration, and HMAC-SHA256 signature."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=24)

    to_encode["iat"] = int(now.timestamp())
    to_encode["exp"] = int(expire.timestamp())
    to_encode["jti"] = secrets.token_hex(8)

    payload_json = json.dumps(to_encode, separators=(",", ":"), sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8").rstrip("=")

    signature = hmac.new(_get_signing_key(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify token signature and expiration, returning decoded claims."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts

        # Check if signature is already revoked
        if signature in _revoked_signatures_cache:
            return None

        # Verify signature with timing-safe comparison
        expected_sig = hmac.new(_get_signing_key(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Base64 decode with proper padding
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        raw_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        claims = json.loads(raw_json)

        # Check expiration
        exp = claims.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            return None

        claims["_sig"] = signature
        return claims
    except Exception:
        return None


def extract_token_signature(token: str) -> Optional[str]:
    """Extract signature part of token for blacklisting."""
    parts = token.split(".")
    return parts[1] if len(parts) == 2 else None


def mark_signature_revoked_in_cache(signature: str) -> None:
    """Add signature to in-memory revocation cache."""
    _revoked_signatures_cache.add(signature)


def discard_signature_from_cache(signature: str) -> None:
    """Remove signature from in-memory revocation cache (e.g. if DB persistence failed)."""
    _revoked_signatures_cache.discard(signature)


def is_signature_revoked_in_cache(signature: str) -> bool:
    """Check if signature is in the revocation cache."""
    return signature in _revoked_signatures_cache


# Rate Limiting
def check_login_rate_limit(identifier: str) -> None:
    """Enforce sliding-window rate limit on failed login attempts."""
    now = datetime.now(timezone.utc).timestamp()
    attempts = _login_failures.get(identifier, [])
    # Filter attempts within lockout window
    recent = [t for t in attempts if now - t < LOCKOUT_WINDOW_SECONDS]
    _login_failures[identifier] = recent

    if len(recent) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts for {identifier}. Account access paused for 5 minutes.",
        )


def record_login_failure(identifier: str) -> None:
    """Record a failed login attempt for rate limiting."""
    now = datetime.now(timezone.utc).timestamp()
    attempts = _login_failures.get(identifier, [])
    attempts.append(now)
    _login_failures[identifier] = attempts


def clear_login_failures(identifier: str) -> None:
    """Clear recorded failures on successful login."""
    _login_failures.pop(identifier, None)
