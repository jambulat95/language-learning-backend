import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.gamification_config import (
    LEVEL_INCREMENT_AFTER_10,
    LEVEL_THRESHOLDS,
)
from app.models.card import Card, CardSet
from app.models.conversation import AIConversation
from app.models.gamification import UserGamification, XpEvent, XpEventType
from app.models.progress import UserCardProgress
from app.models.user import LanguageLevel
from app.schemas.statistics import (
    ActivityResponse,
    DailyActivity,
    LevelPrediction,
    ProgressResponse,
    SetStrength,
    StatisticsOverview,
    StrengthsResponse,
    WeeklyProgress,
)

CEFR_XP_MAP: dict[str, int] = {
    "A1": 0,
    "A2": 2000,
    "B1": 8000,
    "B2": 20000,
    "C1": 45000,
    "C2": 80000,
}

CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _next_level_xp(current_level: int) -> int:
    """XP needed for the next level."""
    next_level = current_level + 1
    if next_level <= len(LEVEL_THRESHOLDS):
        return LEVEL_THRESHOLDS[next_level - 1]
    return LEVEL_THRESHOLDS[-1] + (next_level - len(LEVEL_THRESHOLDS)) * LEVEL_INCREMENT_AFTER_10


def _predict_cefr(
    current_cefr: str, total_xp: int, avg_daily_xp: float,
) -> LevelPrediction:
    """Predict when user will reach the next CEFR level."""
    idx = CEFR_ORDER.index(current_cefr) if current_cefr in CEFR_ORDER else 0
    next_cefr: str | None = CEFR_ORDER[idx + 1] if idx + 1 < len(CEFR_ORDER) else None
    next_cefr_xp: int | None = CEFR_XP_MAP.get(next_cefr) if next_cefr else None

    estimated_date: date | None = None
    if next_cefr_xp is not None and avg_daily_xp > 0:
        remaining = next_cefr_xp - total_xp
        if remaining > 0:
            days_needed = int(remaining / avg_daily_xp)
            estimated_date = (datetime.now(timezone.utc) + timedelta(days=days_needed)).date()
        else:
            estimated_date = datetime.now(timezone.utc).date()

    return LevelPrediction(
        current_cefr=current_cefr,
        next_cefr=next_cefr,
        current_xp=total_xp,
        next_cefr_xp=next_cefr_xp,
        avg_daily_xp=avg_daily_xp,
        estimated_date=estimated_date,
    )


async def get_overview(
    db: AsyncSession, user_id: uuid.UUID, language_level: LanguageLevel,
) -> StatisticsOverview:
    """Get overview statistics for a user."""
    # Words learned (reviewed at least once)
    learned_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .where(UserCardProgress.user_id == user_id, UserCardProgress.total_reviews >= 1)
    )
    words_learned = learned_result.scalar_one()

    # Words mastered (interval >= 21 days)
    mastered_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .where(UserCardProgress.user_id == user_id, UserCardProgress.interval >= 21)
    )
    words_mastered = mastered_result.scalar_one()

    # Accuracy
    accuracy_result = await db.execute(
        select(
            func.coalesce(func.sum(UserCardProgress.correct_reviews), 0),
            func.coalesce(func.sum(UserCardProgress.total_reviews), 0),
        ).where(UserCardProgress.user_id == user_id)
    )
    correct, total = accuracy_result.one()
    accuracy = (correct / total * 100) if total > 0 else 0.0

    # Study days (distinct dates with XP events)
    study_days_result = await db.execute(
        select(func.count(func.distinct(cast(XpEvent.created_at, Date))))
        .where(XpEvent.user_id == user_id)
    )
    study_days = study_days_result.scalar_one()

    # Gamification data
    gam_result = await db.execute(
        select(UserGamification).where(UserGamification.user_id == user_id)
    )
    gam = gam_result.scalar_one_or_none()
    level = gam.level if gam else 1
    total_xp = gam.total_xp if gam else 0
    current_streak = gam.current_streak if gam else 0

    # Avg daily XP over last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    avg_xp_result = await db.execute(
        select(func.coalesce(func.sum(XpEvent.xp_amount), 0))
        .where(XpEvent.user_id == user_id, XpEvent.created_at >= thirty_days_ago)
    )
    xp_last_30 = avg_xp_result.scalar_one()
    avg_daily_xp = xp_last_30 / 30.0

    level_prediction = _predict_cefr(language_level.value, total_xp, avg_daily_xp)

    return StatisticsOverview(
        words_learned=words_learned,
        words_mastered=words_mastered,
        accuracy=round(accuracy, 1),
        study_days=study_days,
        level=level,
        total_xp=total_xp,
        current_streak=current_streak,
        level_prediction=level_prediction,
    )


async def get_activity(
    db: AsyncSession, user_id: uuid.UUID, days: int = 90,
) -> ActivityResponse:
    """Get daily activity for the heatmap."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_date = since.date()

    # XP per day
    xp_result = await db.execute(
        select(
            cast(XpEvent.created_at, Date).label("day"),
            func.sum(XpEvent.xp_amount).label("xp"),
        )
        .where(XpEvent.user_id == user_id, XpEvent.created_at >= since)
        .group_by("day")
    )
    xp_by_day: dict[date, int] = {row.day: row.xp for row in xp_result.all()}

    # Reviews per day (XpEvents of type review)
    reviews_result = await db.execute(
        select(
            cast(XpEvent.created_at, Date).label("day"),
            func.count().label("reviews"),
        )
        .where(
            XpEvent.user_id == user_id,
            XpEvent.event_type == XpEventType.review,
            XpEvent.created_at >= since,
        )
        .group_by("day")
    )
    reviews_by_day: dict[date, int] = {row.day: row.reviews for row in reviews_result.all()}

    # Cards learned per day (UserCardProgress where last_reviewed_at on that day)
    cards_result = await db.execute(
        select(
            cast(UserCardProgress.last_reviewed_at, Date).label("day"),
            func.count().label("cards"),
        )
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.last_reviewed_at >= since,
            UserCardProgress.total_reviews == 1,
        )
        .group_by("day")
    )
    cards_by_day: dict[date, int] = {row.day: row.cards for row in cards_result.all()}

    # Conversations per day
    convos_result = await db.execute(
        select(
            cast(AIConversation.started_at, Date).label("day"),
            func.count().label("convos"),
        )
        .where(AIConversation.user_id == user_id, AIConversation.started_at >= since)
        .group_by("day")
    )
    convos_by_day: dict[date, int] = {row.day: row.convos for row in convos_result.all()}

    # Build full date range
    today = datetime.now(timezone.utc).date()
    activity_days: list[DailyActivity] = []
    current = since_date
    while current <= today:
        activity_days.append(
            DailyActivity(
                date=current,
                xp=xp_by_day.get(current, 0),
                reviews=reviews_by_day.get(current, 0),
                cards_learned=cards_by_day.get(current, 0),
                conversations=convos_by_day.get(current, 0),
            )
        )
        current += timedelta(days=1)

    return ActivityResponse(days=activity_days)


async def get_progress(
    db: AsyncSession, user_id: uuid.UUID, weeks: int = 12,
) -> ProgressResponse:
    """Get weekly XP/reviews/accuracy progress."""
    since = datetime.now(timezone.utc) - timedelta(weeks=weeks)

    # Weekly XP aggregation
    xp_result = await db.execute(
        select(
            func.date_trunc("week", XpEvent.created_at).label("week_start"),
            func.sum(XpEvent.xp_amount).label("xp"),
        )
        .where(XpEvent.user_id == user_id, XpEvent.created_at >= since)
        .group_by("week_start")
        .order_by("week_start")
    )
    xp_rows = xp_result.all()

    # Weekly reviews count
    reviews_result = await db.execute(
        select(
            func.date_trunc("week", XpEvent.created_at).label("week_start"),
            func.count().label("reviews"),
        )
        .where(
            XpEvent.user_id == user_id,
            XpEvent.event_type == XpEventType.review,
            XpEvent.created_at >= since,
        )
        .group_by("week_start")
        .order_by("week_start")
    )
    reviews_rows = reviews_result.all()

    # Weekly accuracy: review events where xp_amount >= 15 count as "correct"
    # (SM-2 quality >= 3 maps to good=20 or easy=25, hard=15, again=10)
    correct_result = await db.execute(
        select(
            func.date_trunc("week", XpEvent.created_at).label("week_start"),
            func.count().label("correct"),
        )
        .where(
            XpEvent.user_id == user_id,
            XpEvent.event_type == XpEventType.review,
            XpEvent.xp_amount >= 15,
            XpEvent.created_at >= since,
        )
        .group_by("week_start")
        .order_by("week_start")
    )
    correct_rows = correct_result.all()

    # Build lookup maps
    xp_map: dict[date, int] = {}
    for row in xp_rows:
        week_date = row.week_start.date() if isinstance(row.week_start, datetime) else row.week_start
        xp_map[week_date] = row.xp

    reviews_map: dict[date, int] = {}
    for row in reviews_rows:
        week_date = row.week_start.date() if isinstance(row.week_start, datetime) else row.week_start
        reviews_map[week_date] = row.reviews

    correct_map: dict[date, int] = {}
    for row in correct_rows:
        week_date = row.week_start.date() if isinstance(row.week_start, datetime) else row.week_start
        correct_map[week_date] = row.correct

    # Build weekly entries covering the full range
    today = datetime.now(timezone.utc).date()
    # Find start of the week (Monday) for `since`
    since_date = since.date()
    # Align to Monday
    start_monday = since_date - timedelta(days=since_date.weekday())

    weekly_entries: list[WeeklyProgress] = []
    current = start_monday
    while current <= today:
        total_reviews = reviews_map.get(current, 0)
        correct_reviews = correct_map.get(current, 0)
        accuracy = (correct_reviews / total_reviews * 100) if total_reviews > 0 else 0.0

        weekly_entries.append(
            WeeklyProgress(
                week_start=current,
                xp=xp_map.get(current, 0),
                reviews=total_reviews,
                accuracy=round(accuracy, 1),
            )
        )
        current += timedelta(weeks=1)

    return ProgressResponse(weeks=weekly_entries)


async def get_strengths(
    db: AsyncSession, user_id: uuid.UUID,
) -> StrengthsResponse:
    """Get per-set accuracy and mastery stats."""
    result = await db.execute(
        select(
            CardSet.id,
            CardSet.title,
            CardSet.card_count,
            func.count(UserCardProgress.id).label("cards_studied"),
            func.coalesce(func.sum(UserCardProgress.correct_reviews), 0).label("correct_reviews"),
            func.coalesce(func.sum(UserCardProgress.total_reviews), 0).label("total_reviews"),
            func.count(
                func.nullif(UserCardProgress.interval < 21, True)
            ).label("mastered_cards"),
        )
        .select_from(CardSet)
        .join(Card, Card.card_set_id == CardSet.id)
        .join(
            UserCardProgress,
            (UserCardProgress.card_id == Card.id) & (UserCardProgress.user_id == user_id),
        )
        .where(CardSet.user_id == user_id)
        .group_by(CardSet.id, CardSet.title, CardSet.card_count)
        .having(func.sum(UserCardProgress.total_reviews) > 0)
    )
    rows = result.all()

    sets: list[SetStrength] = []
    for row in rows:
        accuracy = (row.correct_reviews / row.total_reviews * 100) if row.total_reviews > 0 else 0.0
        sets.append(
            SetStrength(
                set_id=str(row.id),
                set_title=row.title,
                total_cards=row.card_count,
                cards_studied=row.cards_studied,
                correct_reviews=row.correct_reviews,
                total_reviews=row.total_reviews,
                accuracy=round(accuracy, 1),
                mastered_cards=row.mastered_cards,
            )
        )

    # Sort by accuracy descending
    sets.sort(key=lambda s: s.accuracy, reverse=True)

    return StrengthsResponse(sets=sets)
