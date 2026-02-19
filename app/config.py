from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "LangLearn"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://langlearn:langlearn_dev@postgres:5432/langlearn"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    # AI / Mistral
    MISTRAL_API_KEY: str = ""
    MISTRAL_MODEL: str = "mistral-large-latest"
    AI_GENERATION_TEMPERATURE: float = 0.7
    AI_MAX_CARDS_PER_REQUEST: int = 30
    AI_RATE_LIMIT_PER_MINUTE: int = 10
    AI_RATE_LIMIT_PREMIUM_PER_MINUTE: int = 30
    AI_CACHE_TTL_SECONDS: int = 3600

    # AI Conversations
    AI_CONVERSATION_TEMPERATURE: float = 0.8
    AI_GRAMMAR_CHECK_TEMPERATURE: float = 0.3
    AI_CONVERSATION_MAX_TURNS: int = 50
    AI_CONVERSATION_MAX_TOKENS: int = 1024
    AI_FREE_DIALOGUES_PER_WEEK: int = 5

    # Freemium limits
    FREE_MAX_CARD_SETS: int = 10
    FREE_MAX_CARDS_PER_DAY: int = 50

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:80", "http://localhost"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
