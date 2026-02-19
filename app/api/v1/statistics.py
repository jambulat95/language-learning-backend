from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.statistics import (
    ActivityResponse,
    ProgressResponse,
    StatisticsOverview,
    StrengthsResponse,
)
from app.services.statistics_service import (
    get_activity,
    get_overview,
    get_progress,
    get_strengths,
)

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("/overview", response_model=StatisticsOverview)
async def statistics_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_overview(db, current_user.id, current_user.language_level)


@router.get("/activity", response_model=ActivityResponse)
async def statistics_activity(
    days: int = Query(90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_activity(db, current_user.id, days)


@router.get("/progress", response_model=ProgressResponse)
async def statistics_progress(
    weeks: int = Query(12, ge=1, le=52),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_progress(db, current_user.id, weeks)


@router.get("/strengths", response_model=StrengthsResponse)
async def statistics_strengths(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_strengths(db, current_user.id)
