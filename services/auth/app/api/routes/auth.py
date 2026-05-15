from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
    TokenPair,
    TokenRefresh,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.redis_client import (
    get_refresh_token_user_id,
    revoke_refresh_token,
    store_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_tokens(user: User) -> TokenPair:
    access = create_access_token(str(user.id), user.role.value)
    refresh = create_refresh_token(str(user.id), user.role.value)
    payload = decode_token(refresh)
    ttl = settings.refresh_token_expire_days * 24 * 60 * 60
    await store_refresh_token(payload["jti"], user.id, ttl)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    existing = await db.execute(
        select(User).where(User.email == body.email),
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.USER,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
async def login(
    body: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    result = await db.execute(
        select(User).where(User.email == body.email),
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(
        body.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return await _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: TokenRefresh,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    try:
        payload = decode_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    stored_user_id = await get_refresh_token_user_id(jti)
    if stored_user_id is None or stored_user_id != int(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or expired",
        )

    result = await db.execute(
        select(User).where(User.id == int(user_id)),
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        await revoke_refresh_token(jti)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    await revoke_refresh_token(jti)
    return await _issue_tokens(user)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
