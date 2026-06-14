from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    groq_api_key: str
    groq_primary_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    celery_broker_url: str
    celery_result_backend: str

    llm_cache_ttl_seconds: int = 3600

    # Stripe (test mode). secret key only — hosted Checkout needs no publishable key.
    stripe_secret_key: str = ""
    stripe_currency: str = ""  # override; empty = use the account's currency (EGP)
    frontend_base_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
