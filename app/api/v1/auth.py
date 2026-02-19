from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
)
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import (
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    TokenResponse,
    UsageLimitsResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.limits_service import get_usage_limits
from app.services.auth_service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_KEY = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_KEY,
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_KEY,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    existing = await get_user_by_email(db, data.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = await create_user(db, data)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    response.headers["X-Access-Token"] = access_token
    _set_refresh_cookie(response, refresh_token)

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    try:
        user_id = decode_token(refresh_token, expected_type="refresh")
    except JWTError:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    _set_refresh_cookie(response, new_refresh)

    return TokenResponse(access_token=new_access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    _clear_refresh_cookie(response)


@router.post("/password-reset/request")
async def password_reset_request(
    data: PasswordResetRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_email(db, data.email)

    # Always return success to prevent email enumeration
    result: dict = {"message": "If this email exists, a reset link has been sent"}

    if user is not None:
        token = create_password_reset_token(user.id)
        if settings.DEBUG:
            result["reset_token"] = token

    return result


@router.post("/password-reset/confirm")
async def password_reset_confirm(
    data: PasswordResetConfirmSchema,
    db: AsyncSession = Depends(get_db),
):
    try:
        user_id = decode_token(data.token, expected_type="password_reset")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired reset token",
        )

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await update_user_password(db, user, data.new_password)
    return {"message": "Password has been reset successfully"}


@router.get("/usage-limits", response_model=UsageLimitsResponse)
async def usage_limits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_usage_limits(db, current_user)
