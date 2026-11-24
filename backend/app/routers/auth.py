"""Authentication router for UtsavOps operator console."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.operator import Operator
from app.schemas.auth import (
    OperatorLoginRequest,
    OperatorLoginResponse,
    OperatorResponse,
    OperatorMessageResponse,
)
from app.utils.security import hash_password, verify_password, create_access_token, verify_access_token
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
    claims = verify_access_token(token)
    if not claims or "sub" not in claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again.",
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


@router.post("/login", response_model=OperatorLoginResponse)
async def login(payload: OperatorLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate operator and return access token."""
    # Ensure default operator exists on first login attempt
    await ensure_default_operator(db)

    stmt = select(Operator).where(Operator.email == payload.email.strip().lower())
    operator = (await db.execute(stmt)).scalars().first()

    if not operator or not verify_password(payload.password, operator.hashed_password):
        logger.warn("Failed operator login attempt", email=payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your operator credentials.",
        )

    if not operator.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator account is deactivated. Contact platform administrator.",
        )

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
async def logout():
    """Sign out operator and invalidate client session."""
    return OperatorMessageResponse(message="Operator session logged out successfully")


@router.get("/me", response_model=OperatorResponse)
async def get_me(operator: Operator = Depends(get_current_operator)):
    """Retrieve current operator profile."""
    return OperatorResponse.model_validate(operator)
