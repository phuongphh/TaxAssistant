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
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
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
