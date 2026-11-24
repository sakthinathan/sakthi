"""Authentication router for UtsavOps operator console."""
from datetime import datetime, timezone
from typing import Optional, Callable
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.operator import Operator, RevokedToken
from app.schemas.auth import (
    OperatorLoginRequest,
    OperatorLoginResponse,
    OperatorResponse,
    OperatorMessageResponse,
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
    extract_token_signature,
    mark_signature_revoked_in_cache,
    is_signature_revoked_in_cache,
    check_login_rate_limit,
    record_login_failure,
    clear_login_failures,
)
import structlog

logger = structlog.get_logger()
router = APIRouter()

DEFAULT_ADMIN_EMAIL = "admin@utsavops.internal"
DEFAULT_ADMIN_PASSWORD = "UtsavOps2026!Secure"
DEFAULT_ADMIN_NAME = "UtsavOps Lead SRE"


async def ensure_default_operator(db: AsyncSession) -> Operator:
    """Ensure the default seeded operator exists in the database."""
    stmt = select(Operator).where(Operator.email == DEFAULT_ADMIN_EMAIL)
    operator = (await db.execute(stmt)).scalars().first()
    if not operator:
        operator = Operator(
            email=DEFAULT_ADMIN_EMAIL,
            hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
            name=DEFAULT_ADMIN_NAME,
            role="admin",
            is_active=True,
        )
        db.add(operator)
        await db.commit()
        await db.refresh(operator)
        logger.info("Default operator seeded successfully", email=DEFAULT_ADMIN_EMAIL)
    return operator


async def get_current_operator(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> Operator:
    """Dependency to retrieve currently authenticated operator from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()

    # Check in-memory revocation cache first
    sig = extract_token_signature(token)
    if sig and is_signature_revoked_in_cache(sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked or logged out. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check database revocation if signature present
    if sig:
        rev_check = await db.execute(select(RevokedToken).where(RevokedToken.token_signature == sig))
        if rev_check.scalars().first():
            mark_signature_revoked_in_cache(sig)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked or logged out. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    claims = verify_access_token(token)
    if not claims or "sub" not in claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or tampered session token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    operator_id = claims["sub"]
    stmt = select(Operator).where(Operator.id == operator_id)
    operator = (await db.execute(stmt)).scalars().first()

    if not operator or not operator.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operator account not found or inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return operator


def require_roles(*allowed_roles: str) -> Callable:
    """Role-Based Access Control dependency factory."""
    async def role_checker(operator: Operator = Depends(get_current_operator)) -> Operator:
        if operator.role not in allowed_roles:
            logger.warn(
                "Access denied for operator role",
                operator_id=operator.id,
                email=operator.email,
                actual_role=operator.role,
                allowed_roles=allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required role: {', '.join(allowed_roles)}. Your role is '{operator.role}'.",
            )
        return operator

    return role_checker


@router.post("/login", response_model=OperatorLoginResponse)
async def login(payload: OperatorLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate operator with rate-limiting and return access token."""
    clean_email = payload.email.strip().lower()

    # Rate limiting on failed login attempts
    check_login_rate_limit(clean_email)

    # Ensure default operator exists on first login attempt
    await ensure_default_operator(db)

    stmt = select(Operator).where(Operator.email == clean_email)
    operator = (await db.execute(stmt)).scalars().first()

    if not operator or not verify_password(payload.password, operator.hashed_password):
        record_login_failure(clean_email)
        logger.warn("Failed operator login attempt", email=clean_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your operator credentials.",
        )

    if not operator.is_active:
        logger.warn("Deactivated operator login attempt", email=clean_email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator account is deactivated. Contact platform administrator.",
        )

    # Success: clear failed rate-limit counter
    clear_login_failures(clean_email)

    operator.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(operator)

    token = create_access_token(data={"sub": operator.id, "email": operator.email, "role": operator.role})

    logger.info("Operator logged in successfully", email=operator.email, role=operator.role)
    return OperatorLoginResponse(
        access_token=token,
        token_type="bearer",
        operator=OperatorResponse.model_validate(operator),
        message="Authentication successful",
    )


@router.post("/logout", response_model=OperatorMessageResponse)
async def logout(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
):
    """Sign out operator and revoke token on server side."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        sig = extract_token_signature(token)
        claims = verify_access_token(token)
        if sig:
            mark_signature_revoked_in_cache(sig)
            exp_timestamp = claims.get("exp") if claims else None
            expires_at = (
                datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                if exp_timestamp
                else datetime.now(timezone.utc)
            )
            # Persist revoked token signature to database
            revoked_entry = RevokedToken(
                token_signature=sig,
                expires_at=expires_at,
            )
            db.add(revoked_entry)
            try:
                await db.commit()
            except Exception as e:
                logger.warn("Revoked token save warning", error=str(e))

    return OperatorMessageResponse(message="Operator session logged out and token revoked successfully")


@router.get("/me", response_model=OperatorResponse)
async def get_me(operator: Operator = Depends(get_current_operator)):
    """Retrieve current operator profile."""
    return OperatorResponse.model_validate(operator)
