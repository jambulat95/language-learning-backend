import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.user_interest import UserInterest
from app.schemas.user import UserRegisterRequest, UserUpdateRequest


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.interests))
        .where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.interests))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserRegisterRequest) -> User:
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        native_language=data.native_language,
        language_level=data.language_level,
    )
    db.add(user)
    await db.flush()

    for interest_name in data.interests:
        interest = UserInterest(user_id=user.id, interest=interest_name)
        db.add(interest)
    await db.flush()

    # Reload with interests
    return await get_user_by_id(db, user.id)  # type: ignore[return-value]


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdateRequest) -> User:
    update_data = data.model_dump(exclude_unset=True, exclude={"interests"})
    for field, value in update_data.items():
        setattr(user, field, value)

    if data.interests is not None:
        # Replace all interests
        for old_interest in user.interests:
            await db.delete(old_interest)
        await db.flush()
        for interest_name in data.interests:
            interest = UserInterest(user_id=user.id, interest=interest_name)
            db.add(interest)

    await db.flush()
    return await get_user_by_id(db, user.id)  # type: ignore[return-value]


async def update_user_password(db: AsyncSession, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    await db.flush()
