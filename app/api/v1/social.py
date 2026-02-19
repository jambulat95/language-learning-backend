import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.social import (
    FriendProgressResponse,
    FriendResponse,
    FriendshipResponse,
    SendFriendRequestRequest,
    ShareCardSetRequest,
    SharedCardSetResponse,
    UserSearchResult,
)
from app.services import social_service

router = APIRouter(prefix="/social", tags=["social"])


# ── Friend Requests ─────────────────────────────────────────────────────────


@router.post(
    "/friend-requests",
    response_model=FriendshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_friend_request(
    body: SendFriendRequestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FriendshipResponse:
    return await social_service.send_friend_request(
        db, current_user.id, body.friend_id
    )


@router.get(
    "/friend-requests/incoming",
    response_model=list[FriendshipResponse],
)
async def get_incoming_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FriendshipResponse]:
    return await social_service.get_pending_requests(db, current_user.id)


@router.post(
    "/friend-requests/{friendship_id}/accept",
    response_model=FriendshipResponse,
)
async def accept_friend_request(
    friendship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FriendshipResponse:
    return await social_service.accept_friend_request(
        db, friendship_id, current_user.id
    )


@router.delete(
    "/friend-requests/{friendship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reject_friend_request(
    friendship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await social_service.reject_friend_request(db, friendship_id, current_user.id)


# ── Friends ──────────────────────────────────────────────────────────────────


@router.get(
    "/friends",
    response_model=list[FriendResponse],
)
async def get_friends(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FriendResponse]:
    return await social_service.get_friends(db, current_user.id)


@router.delete(
    "/friends/{friendship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_friend(
    friendship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await social_service.remove_friend(db, friendship_id, current_user.id)


@router.get(
    "/friends/{user_id}/progress",
    response_model=FriendProgressResponse,
)
async def get_friend_progress(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FriendProgressResponse:
    return await social_service.get_friend_progress(db, current_user.id, user_id)


# ── User Search ──────────────────────────────────────────────────────────────


@router.get(
    "/users/search",
    response_model=list[UserSearchResult],
)
async def search_users(
    q: str = Query(..., min_length=2, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserSearchResult]:
    return await social_service.search_users(db, q, current_user.id)


# ── Card Set Sharing ─────────────────────────────────────────────────────────


@router.post(
    "/card-sets/{set_id}/share",
    response_model=SharedCardSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def share_card_set(
    set_id: uuid.UUID,
    body: ShareCardSetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SharedCardSetResponse:
    return await social_service.share_card_set(
        db, set_id, current_user.id, body.friend_id
    )


@router.delete(
    "/shared-sets/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unshare_card_set(
    share_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await social_service.unshare_card_set(db, share_id, current_user.id)


@router.get(
    "/shared-sets/incoming",
    response_model=list[SharedCardSetResponse],
)
async def get_shared_with_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SharedCardSetResponse]:
    return await social_service.get_shared_with_me(db, current_user.id)


@router.get(
    "/shared-sets/outgoing",
    response_model=list[SharedCardSetResponse],
)
async def get_my_shared(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SharedCardSetResponse]:
    return await social_service.get_my_shared(db, current_user.id)
