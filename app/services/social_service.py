import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.gamification_config import XP_FRIEND_ADDED
from app.models.card import CardSet
from app.models.friendship import Friendship, FriendshipStatus
from app.models.gamification import UserGamification, XpEventType
from app.models.progress import UserCardProgress
from app.models.shared_card_set import SharedCardSet
from app.models.user import User
from app.schemas.social import (
    FriendGamificationStats,
    FriendProgressResponse,
    FriendResponse,
    FriendshipResponse,
    FriendStudyStats,
    FriendUserInfo,
    SharedByInfo,
    SharedCardSetInfo,
    SharedCardSetResponse,
    UserSearchResult,
)


# ── Friendships ──────────────────────────────────────────────────────────────


async def send_friend_request(
    db: AsyncSession, user_id: uuid.UUID, friend_id: uuid.UUID
) -> FriendshipResponse:
    """Send a friend request to another user."""
    if user_id == friend_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send friend request to yourself",
        )

    # Check that target user exists
    friend = await db.get(User, friend_id)
    if friend is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check for existing friendship in either direction
    existing = await db.execute(
        select(Friendship).where(
            or_(
                and_(
                    Friendship.user_id == user_id,
                    Friendship.friend_id == friend_id,
                ),
                and_(
                    Friendship.user_id == friend_id,
                    Friendship.friend_id == user_id,
                ),
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Friendship or pending request already exists",
        )

    friendship = Friendship(
        user_id=user_id,
        friend_id=friend_id,
        status=FriendshipStatus.pending,
    )
    db.add(friendship)
    await db.flush()

    sender = await db.get(User, user_id)
    return FriendshipResponse(
        id=friendship.id,
        user=FriendUserInfo(
            id=sender.id,
            full_name=sender.full_name,
            avatar_url=sender.avatar_url,
            language_level=sender.language_level,
        ),
        status=friendship.status,
        created_at=friendship.created_at,
    )


async def accept_friend_request(
    db: AsyncSession, friendship_id: uuid.UUID, current_user_id: uuid.UUID
) -> FriendshipResponse:
    """Accept an incoming friend request."""
    friendship = await db.get(Friendship, friendship_id)
    if friendship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found"
        )
    if friendship.friend_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the recipient can accept a friend request",
        )
    if friendship.status != FriendshipStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Friend request is not pending",
        )

    friendship.status = FriendshipStatus.accepted
    await db.flush()

    # Award XP to both users
    from app.services.gamification_service import award_xp

    sender = await db.get(User, friendship.user_id)
    recipient = await db.get(User, friendship.friend_id)
    await award_xp(db, sender, XP_FRIEND_ADDED, XpEventType.friend_added)
    await award_xp(db, recipient, XP_FRIEND_ADDED, XpEventType.friend_added)

    return FriendshipResponse(
        id=friendship.id,
        user=FriendUserInfo(
            id=sender.id,
            full_name=sender.full_name,
            avatar_url=sender.avatar_url,
            language_level=sender.language_level,
        ),
        status=friendship.status,
        created_at=friendship.created_at,
    )


async def reject_friend_request(
    db: AsyncSession, friendship_id: uuid.UUID, current_user_id: uuid.UUID
) -> None:
    """Reject or cancel a pending friend request."""
    friendship = await db.get(Friendship, friendship_id)
    if friendship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found"
        )
    # Either party can cancel/reject a pending request
    if friendship.user_id != current_user_id and friendship.friend_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this friend request",
        )
    if friendship.status != FriendshipStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Friend request is not pending",
        )

    await db.delete(friendship)
    await db.flush()


async def remove_friend(
    db: AsyncSession, friendship_id: uuid.UUID, current_user_id: uuid.UUID
) -> None:
    """Remove an accepted friendship. Either party can remove."""
    friendship = await db.get(Friendship, friendship_id)
    if friendship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friendship not found"
        )
    if friendship.user_id != current_user_id and friendship.friend_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to remove this friendship",
        )
    if friendship.status != FriendshipStatus.accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is not an accepted friendship",
        )

    await db.delete(friendship)
    await db.flush()


async def get_pending_requests(
    db: AsyncSession, user_id: uuid.UUID
) -> list[FriendshipResponse]:
    """Get incoming pending friend requests for the current user."""
    result = await db.execute(
        select(Friendship)
        .where(
            Friendship.friend_id == user_id,
            Friendship.status == FriendshipStatus.pending,
        )
        .order_by(Friendship.created_at.desc())
    )
    friendships = result.scalars().all()

    responses = []
    for f in friendships:
        sender = await db.get(User, f.user_id)
        responses.append(
            FriendshipResponse(
                id=f.id,
                user=FriendUserInfo(
                    id=sender.id,
                    full_name=sender.full_name,
                    avatar_url=sender.avatar_url,
                    language_level=sender.language_level,
                ),
                status=f.status,
                created_at=f.created_at,
            )
        )
    return responses


async def get_friends(
    db: AsyncSession, user_id: uuid.UUID
) -> list[FriendResponse]:
    """Get all accepted friends for the current user."""
    result = await db.execute(
        select(Friendship).where(
            or_(
                Friendship.user_id == user_id,
                Friendship.friend_id == user_id,
            ),
            Friendship.status == FriendshipStatus.accepted,
        )
    )
    friendships = result.scalars().all()

    responses = []
    for f in friendships:
        # The friend is the other person in the friendship
        friend_user_id = f.friend_id if f.user_id == user_id else f.user_id
        friend = await db.get(User, friend_user_id)
        responses.append(
            FriendResponse(
                id=friend.id,
                full_name=friend.full_name,
                avatar_url=friend.avatar_url,
                language_level=friend.language_level,
                is_premium=friend.is_premium,
            )
        )
    return responses


async def search_users(
    db: AsyncSession, query: str, current_user_id: uuid.UUID
) -> list[UserSearchResult]:
    """Search users by name or email, excluding self."""
    search_pattern = f"%{query}%"
    result = await db.execute(
        select(User)
        .where(
            User.id != current_user_id,
            User.is_active == True,  # noqa: E712
            or_(
                User.full_name.ilike(search_pattern),
                User.email.ilike(search_pattern),
            ),
        )
        .limit(20)
    )
    users = result.scalars().all()

    # Get existing friendships for the current user with these users
    user_ids = [u.id for u in users]
    if user_ids:
        friendships_result = await db.execute(
            select(Friendship).where(
                or_(
                    and_(
                        Friendship.user_id == current_user_id,
                        Friendship.friend_id.in_(user_ids),
                    ),
                    and_(
                        Friendship.user_id.in_(user_ids),
                        Friendship.friend_id == current_user_id,
                    ),
                )
            )
        )
        friendships = friendships_result.scalars().all()
        # Map user_id -> friendship
        friendship_map: dict[uuid.UUID, Friendship] = {}
        for f in friendships:
            other_id = f.friend_id if f.user_id == current_user_id else f.user_id
            friendship_map[other_id] = f
    else:
        friendship_map = {}

    responses = []
    for u in users:
        f = friendship_map.get(u.id)
        responses.append(
            UserSearchResult(
                id=u.id,
                full_name=u.full_name,
                avatar_url=u.avatar_url,
                language_level=u.language_level,
                friendship_status=f.status if f else None,
                friendship_id=f.id if f else None,
            )
        )
    return responses


# ── Card Set Sharing ─────────────────────────────────────────────────────────


async def _validate_friendship(
    db: AsyncSession, user_id: uuid.UUID, friend_id: uuid.UUID
) -> None:
    """Validate that an accepted friendship exists between two users."""
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(
                    Friendship.user_id == user_id,
                    Friendship.friend_id == friend_id,
                ),
                and_(
                    Friendship.user_id == friend_id,
                    Friendship.friend_id == user_id,
                ),
            ),
            Friendship.status == FriendshipStatus.accepted,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only share with friends",
        )


async def share_card_set(
    db: AsyncSession,
    card_set_id: uuid.UUID,
    shared_by_id: uuid.UUID,
    friend_id: uuid.UUID,
) -> SharedCardSetResponse:
    """Share a card set with a friend."""
    # Validate friendship
    await _validate_friendship(db, shared_by_id, friend_id)

    # Validate card set ownership
    card_set = await db.get(CardSet, card_set_id)
    if card_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card set not found"
        )
    if card_set.user_id != shared_by_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only share your own card sets",
        )

    # Check for duplicate share
    existing = await db.execute(
        select(SharedCardSet).where(
            SharedCardSet.card_set_id == card_set_id,
            SharedCardSet.shared_with_id == friend_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Card set already shared with this user",
        )

    shared = SharedCardSet(
        card_set_id=card_set_id,
        shared_by_id=shared_by_id,
        shared_with_id=friend_id,
    )
    db.add(shared)
    await db.flush()

    sharer = await db.get(User, shared_by_id)
    return SharedCardSetResponse(
        id=shared.id,
        card_set=SharedCardSetInfo(
            id=card_set.id,
            title=card_set.title,
            card_count=card_set.card_count,
            difficulty_level=card_set.difficulty_level,
        ),
        shared_by=SharedByInfo(
            id=sharer.id,
            full_name=sharer.full_name,
            avatar_url=sharer.avatar_url,
        ),
        created_at=shared.created_at,
    )


async def unshare_card_set(
    db: AsyncSession, share_id: uuid.UUID, current_user_id: uuid.UUID
) -> None:
    """Remove a shared card set. Only the sharer can unshare."""
    shared = await db.get(SharedCardSet, share_id)
    if shared is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shared card set not found"
        )
    if shared.shared_by_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the sharer can unshare a card set",
        )

    await db.delete(shared)
    await db.flush()


async def get_shared_with_me(
    db: AsyncSession, user_id: uuid.UUID
) -> list[SharedCardSetResponse]:
    """Get card sets shared with the current user."""
    result = await db.execute(
        select(SharedCardSet)
        .where(SharedCardSet.shared_with_id == user_id)
        .order_by(SharedCardSet.created_at.desc())
    )
    shares = result.scalars().all()

    responses = []
    for s in shares:
        card_set = await db.get(CardSet, s.card_set_id)
        sharer = await db.get(User, s.shared_by_id)
        if card_set and sharer:
            responses.append(
                SharedCardSetResponse(
                    id=s.id,
                    card_set=SharedCardSetInfo(
                        id=card_set.id,
                        title=card_set.title,
                        card_count=card_set.card_count,
                        difficulty_level=card_set.difficulty_level,
                    ),
                    shared_by=SharedByInfo(
                        id=sharer.id,
                        full_name=sharer.full_name,
                        avatar_url=sharer.avatar_url,
                    ),
                    created_at=s.created_at,
                )
            )
    return responses


async def get_my_shared(
    db: AsyncSession, user_id: uuid.UUID
) -> list[SharedCardSetResponse]:
    """Get card sets the current user has shared with others."""
    result = await db.execute(
        select(SharedCardSet)
        .where(SharedCardSet.shared_by_id == user_id)
        .order_by(SharedCardSet.created_at.desc())
    )
    shares = result.scalars().all()

    responses = []
    for s in shares:
        card_set = await db.get(CardSet, s.card_set_id)
        sharer = await db.get(User, s.shared_by_id)
        if card_set and sharer:
            responses.append(
                SharedCardSetResponse(
                    id=s.id,
                    card_set=SharedCardSetInfo(
                        id=card_set.id,
                        title=card_set.title,
                        card_count=card_set.card_count,
                        difficulty_level=card_set.difficulty_level,
                    ),
                    shared_by=SharedByInfo(
                        id=sharer.id,
                        full_name=sharer.full_name,
                        avatar_url=sharer.avatar_url,
                    ),
                    created_at=s.created_at,
                )
            )
    return responses


# ── Friend Progress ──────────────────────────────────────────────────────────


async def get_friend_progress(
    db: AsyncSession, current_user_id: uuid.UUID, friend_id: uuid.UUID
) -> FriendProgressResponse:
    """Get a friend's public progress stats."""
    # Validate friendship exists
    await _validate_friendship(db, current_user_id, friend_id)

    friend = await db.get(User, friend_id)
    if friend is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get gamification stats
    gam_result = await db.execute(
        select(UserGamification).where(UserGamification.user_id == friend_id)
    )
    gam = gam_result.scalar_one_or_none()

    gamification = FriendGamificationStats(
        total_xp=gam.total_xp if gam else 0,
        level=gam.level if gam else 1,
        league=gam.league if gam else "Bronze",
        current_streak=gam.current_streak if gam else 0,
        longest_streak=gam.longest_streak if gam else 0,
    )

    # Get study stats
    words_learned_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .where(UserCardProgress.user_id == friend_id)
    )
    words_learned = words_learned_result.scalar_one()

    # Mastered = interval >= 21 days (well-known threshold)
    words_mastered_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .where(
            UserCardProgress.user_id == friend_id,
            UserCardProgress.interval >= 21,
        )
    )
    words_mastered = words_mastered_result.scalar_one()

    # Study days = distinct dates with activity
    from app.models.gamification import XpEvent

    study_days_result = await db.execute(
        select(func.count(func.distinct(func.date(XpEvent.created_at))))
        .where(XpEvent.user_id == friend_id)
    )
    study_days = study_days_result.scalar_one()

    # Accuracy = correct_reviews / total_reviews
    accuracy_result = await db.execute(
        select(
            func.coalesce(func.sum(UserCardProgress.correct_reviews), 0),
            func.coalesce(func.sum(UserCardProgress.total_reviews), 0),
        ).where(UserCardProgress.user_id == friend_id)
    )
    correct, total = accuracy_result.one()
    accuracy = (correct / total * 100) if total > 0 else 0.0

    study = FriendStudyStats(
        words_learned=words_learned,
        words_mastered=words_mastered,
        study_days=study_days,
        accuracy=round(accuracy, 1),
    )

    return FriendProgressResponse(
        id=friend.id,
        full_name=friend.full_name,
        avatar_url=friend.avatar_url,
        language_level=friend.language_level,
        is_premium=friend.is_premium,
        gamification=gamification,
        study=study,
    )
