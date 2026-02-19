from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.config import settings
from app.core.seed_achievements import seed_achievements
from app.database import async_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(
        settings.REDIS_URL, decode_responses=True,
    )
    # Seed achievements on startup
    async with async_session_factory() as session:
        await seed_achievements(session)
    yield
    await app.state.redis.close()


app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Access-Token"],
)

app.include_router(api_v1_router)


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
