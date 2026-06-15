import re

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    # Redis/Celery aren't used at runtime (no worker); default so deploys don't
    # need to set them.
    redis_url: str = "redis://localhost:6379"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    groq_api_key: str
    groq_primary_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    # "local" = sentence-transformers (PyTorch, needs ~1GB RAM); "hf" = HuggingFace
    # Inference API (no torch — used in lightweight free-tier deploys). Same model
    # either way, so stored 384-dim vectors stay compatible.
    embedding_backend: str = "local"
    hf_api_token: str = ""

    # Extra CORS origins (comma-separated) — your deployed frontend URLs.
    cors_origins: str = ""

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    llm_cache_ttl_seconds: int = 3600

    # Two-factor: demo delivery shows the login OTP on screen (no email wired).
    # Set false once you deliver it via email/SMS instead.
    otp_demo_show_code: bool = True

    # Stripe (test mode). secret key only — hosted Checkout needs no publishable key.
    stripe_secret_key: str = ""
    stripe_currency: str = ""  # override; empty = use the account's currency (EGP)
    frontend_base_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Accept any host's Postgres URL and coerce it to the async driver, so
        you can paste Render/Neon/Railway's string verbatim (no manual editing)."""
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        # asyncpg doesn't accept libpq's ?sslmode= arg — drop it (it negotiates SSL).
        return re.sub(r"[?&]sslmode=[^&]*", "", v)


settings = Settings()
