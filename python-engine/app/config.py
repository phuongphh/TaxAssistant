from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    environment: str = "development"
    debug: bool = True

    # Server
    rest_host: str = "0.0.0.0"
    rest_port: int = 8000
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051

    # Database
    postgres_url: str = "postgresql+asyncpg://taxapp:taxapp_dev@localhost:5432/taxassistant"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # LLM / AI
    # Provider: "anthropic" or "openai_compatible" (for Z.AI, OpenRouter, etc.)
    llm_provider: str = "openai_compatible"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.z.ai/api/paas/v4/"
    llm_model: str = "glm-5"
    llm_temperature: float = 0.3
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"

    # Document Processing
    tesseract_lang: str = "vie"
    max_upload_size_mb: int = 10

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
