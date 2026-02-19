from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.ai import router as ai_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cards import router as cards_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.gamification import router as gamification_router
from app.api.v1.social import router as social_router
from app.api.v1.srs import router as srs_router
from app.api.v1.statistics import router as statistics_router
from app.api.v1.users import router as users_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(admin_router)
api_v1_router.include_router(ai_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(cards_router)
api_v1_router.include_router(srs_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(gamification_router)
api_v1_router.include_router(conversations_router)
api_v1_router.include_router(social_router)
api_v1_router.include_router(statistics_router)
