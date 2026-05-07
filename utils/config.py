from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    OLLAMA_MODEL: str = "llama3.2:1b"
    EMBEDDING_MODEL: str = "qwen3-embedding:0.6b-fp16"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT__SERVICE__API_KEY: str = "your_qdrant_api_key"
    QDRANT_COLLECTION_NAME: str = "pdf_rag"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
