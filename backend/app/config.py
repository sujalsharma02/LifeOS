from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    llm_provider: str = "nvidia"
    # If the primary provider is unavailable (missing key or API error), fall back to this one.
    llm_fallback_provider: str = "gemini"

    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_chat_model: str = "meta/llama-3.3-70b-instruct"
    nvidia_embedding_model: str = "nvidia/nv-embedqa-e5-v5"
    # NVIDIA Build's free tier can queue requests for minutes; past this window we
    # treat it as unavailable and use the fallback provider instead.
    nvidia_timeout_seconds: float = 45

    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-3.5-flash"
    # Tried when the main Gemini model stays overloaded (503) after retries.
    # Set empty to disable. Flagship flash models get demand spikes; lite rarely does.
    gemini_fallback_model: str = "gemini-flash-lite-latest"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    # Optional: use a dedicated embedding provider (e.g. "voyage") while chat stays on llm_provider.
    embedding_provider: str = ""
    voyage_api_key: str = ""
    voyage_embedding_model: str = "voyage-3.5"

    cors_origins: str = "http://localhost:3000"

    # Google Sign-In. When google_client_id is empty, auth is disabled and the app
    # runs in single-user mode (everything belongs to one default user).
    google_client_id: str = ""
    auth_secret: str = "change-me-in-production"
    auth_token_days: int = 30

    @property
    def async_database_url(self) -> str:
        """Neon gives a postgresql:// URL; SQLAlchemy async needs the asyncpg driver.

        asyncpg does not understand libpq-only query params (sslmode, channel_binding),
        so translate/strip them.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("sslmode=require", "ssl=require")
        for param in ("&channel_binding=require", "?channel_binding=require"):
            url = url.replace(param, "")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
