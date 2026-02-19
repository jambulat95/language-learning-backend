import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.srs import (
    ReviewRequest,
    ReviewResponse,
    StudyCardResponse,
    StudySetProgressResponse,
)
from app.services.srs_service import (
    get_due_cards,
    get_set_study_progress,
    submit_review,
)

router = APIRouter(prefix="/study", tags=["study"])


@router.get("/sets/{set_id}/due-cards", response_model=list[StudyCardResponse])
async def get_due_cards_endpoint(
    set_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    new_first: bool = Query(True),
    practice: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_due_cards(db, current_user, set_id, limit=limit, new_first=new_first, practice=practice)


@router.post("/review", response_model=ReviewResponse)
async def submit_review_endpoint(
    data: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await submit_review(db, current_user, data.card_id, data.rating)


@router.get("/sets/{set_id}/progress", response_model=StudySetProgressResponse)
async def get_study_progress_endpoint(
    set_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_set_study_progress(db, current_user, set_id)
