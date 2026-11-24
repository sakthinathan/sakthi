"""Security utility functions for password hashing and token generation."""
import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from app.config import get_settings

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 100_000

def _get_signing_key() -> bytes:
    settings = get_settings()
    raw_secret = settings.gemini_api_key or "utsavops-secure-token-signing-key-2026"
    return raw_secret.encode("utf-8")

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS,
    )
    return f"{ALGORITHM}${ITERATIONS}${salt}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored PBKDF2 hash."""
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
    """Create a signed URL-safe token with expiration and HMAC-SHA256 signature."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode["exp"] = int(expire.timestamp())

    payload_json = json.dumps(to_encode, separators=(",", ":"), sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8").rstrip("=")

    signature = hmac.new(_get_signing_key(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify signed token signature and expiration, returning decoded claims."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts

        # Verify signature
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

        return claims
    except Exception:
        return None
