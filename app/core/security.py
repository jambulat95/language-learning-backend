import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    to_encode["jti"] = uuid.uuid4().hex
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(
        {"sub": str(user_id), "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(
        {"sub": str(user_id), "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_password_reset_token(user_id: uuid.UUID) -> str:
    return _create_token(
        {"sub": str(user_id), "type": "password_reset"},
        timedelta(minutes=30),
    )


def decode_token(token: str, expected_type: str) -> uuid.UUID:
    """Decode and validate a JWT token. Returns the user UUID.

    Raises JWTError on any validation failure.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise

    if payload.get("type") != expected_type:
        raise JWTError(f"Invalid token type: expected {expected_type}")

    sub = payload.get("sub")
    if sub is None:
        raise JWTError("Token missing subject")

    try:
        return uuid.UUID(sub)
    except ValueError:
        raise JWTError("Invalid subject in token")
