import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_db
from app.models.user import User
from app.schemas.admin import (
    AdminUserResponse,
    AdminUserUpdateRequest,
    PaginatedAdminCardSetResponse,
    PaginatedAdminUserResponse,
    PlatformStatsResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=PlatformStatsResponse)
async def get_platform_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> PlatformStatsResponse:
    return await admin_service.get_platform_stats(db)


@router.get("/users", response_model=PaginatedAdminUserResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> PaginatedAdminUserResponse:
    return await admin_service.list_users(db, skip, limit, search)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> AdminUserResponse:
    return await admin_service.update_user_admin(db, user_id, body)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> None:
    await admin_service.delete_user(db, user_id)


@router.get("/card-sets", response_model=PaginatedAdminCardSetResponse)
async def list_public_card_sets(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> PaginatedAdminCardSetResponse:
    return await admin_service.list_public_card_sets(db, skip, limit, search)


@router.delete(
    "/card-sets/{set_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_card_set(
    set_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> None:
    await admin_service.delete_card_set_admin(db, set_id)
