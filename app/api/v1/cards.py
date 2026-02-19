import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.card import CardType
from app.models.user import LanguageLevel, User
from app.schemas.card import (
    CardBulkCreate,
    CardBulkResponse,
    CardCreate,
    CardImportResponse,
    CardResponse,
    CardSetCreate,
    CardSetDetailResponse,
    CardSetResponse,
    CardSetUpdate,
    CardUpdate,
    PaginatedCardResponse,
    PaginatedCardSetResponse,
)
from app.services.card_service import (
    bulk_create_cards,
    create_card,
    create_card_set,
    delete_card,
    delete_card_set,
    get_card,
    get_card_set_for_owner,
    get_card_set_or_public,
    import_cards_from_file,
    list_cards,
    list_public_card_sets,
    list_user_card_sets,
    update_card,
    update_card_set,
)

router = APIRouter(prefix="/card-sets", tags=["card-sets"])


# --- CardSet endpoints ---

@router.post("", response_model=CardSetResponse, status_code=status.HTTP_201_CREATED)
async def create_card_set_endpoint(
    data: CardSetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_card_set(db, data, current_user)


@router.get("", response_model=PaginatedCardSetResponse)
async def list_my_card_sets(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=200),
    category: str | None = None,
    difficulty_level: LanguageLevel | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await list_user_card_sets(
        db, current_user, skip=skip, limit=limit, q=q,
        category=category, difficulty_level=difficulty_level,
    )
    return PaginatedCardSetResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/public", response_model=PaginatedCardSetResponse)
async def list_public_card_sets_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=200),
    category: str | None = None,
    difficulty_level: LanguageLevel | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await list_public_card_sets(
        db, skip=skip, limit=limit, q=q,
        category=category, difficulty_level=difficulty_level,
    )
    return PaginatedCardSetResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{set_id}", response_model=CardSetDetailResponse)
async def get_card_set_detail(
    set_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_card_set_or_public(db, set_id, current_user)


@router.patch("/{set_id}", response_model=CardSetResponse)
async def update_card_set_endpoint(
    set_id: uuid.UUID,
    data: CardSetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = await get_card_set_for_owner(db, set_id, current_user)
    return await update_card_set(db, card_set, data)


@router.delete("/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card_set_endpoint(
    set_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = await get_card_set_for_owner(db, set_id, current_user)
    await delete_card_set(db, card_set)


# --- Card endpoints ---

@router.post(
    "/{set_id}/cards", response_model=CardResponse, status_code=status.HTTP_201_CREATED,
)
async def create_card_endpoint(
    set_id: uuid.UUID,
    data: CardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = await get_card_set_for_owner(db, set_id, current_user)
    return await create_card(db, card_set, data, current_user)


@router.get("/{set_id}/cards", response_model=PaginatedCardResponse)
async def list_cards_endpoint(
    set_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, max_length=200),
    card_type: CardType | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = await get_card_set_or_public(db, set_id, current_user)
    items, total = await list_cards(
        db, card_set, skip=skip, limit=limit, q=q, card_type=card_type,
    )
    return PaginatedCardResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{set_id}/cards/{card_id}", response_model=CardResponse)
async def get_card_endpoint(
    set_id: uuid.UUID,
    card_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = await get_card_set_or_public(db, set_id, current_user)
    return await get_card(db, card_set, card_id)


@router.patch("/{set_id}/cards/{card_id}", response_model=CardResponse)
async def update_card_endpoint(
    set_id: uuid.UUID,
    card_id: uuid.UUID,
    data: CardUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = await get_card_set_for_owner(db, set_id, current_user)
    card = await get_card(db, card_set, card_id)
    return await update_card(db, card, data)


@router.delete("/{set_id}/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card_endpoint(
    set_id: uuid.UUID,
    card_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = await get_card_set_for_owner(db, set_id, current_user)
    card = await get_card(db, card_set, card_id)
    await delete_card(db, card)


@router.post(
    "/{set_id}/cards/bulk",
    response_model=CardBulkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_cards_endpoint(
    set_id: uuid.UUID,
    data: CardBulkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = await get_card_set_for_owner(db, set_id, current_user)
    cards = await bulk_create_cards(db, card_set, data, current_user)
    return CardBulkResponse(created_count=len(cards), cards=cards)


@router.post(
    "/{set_id}/cards/import",
    response_model=CardImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_cards_endpoint(
    set_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = await get_card_set_for_owner(db, set_id, current_user)
    cards, skipped = await import_cards_from_file(db, card_set, file, current_user)
    return CardImportResponse(
        imported_count=len(cards), skipped_count=skipped, cards=cards,
    )
