"""Application configuration from environment."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")

    bedrock_reasoning_model_id: str = Field(
        default="anthropic.claude-3-5-sonnet-20240620-v1:0",
        alias="BEDROCK_REASONING_MODEL_ID",
    )
    bedrock_embedding_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0",
        alias="BEDROCK_EMBEDDING_MODEL_ID",
    )
    bedrock_embedding_dimension: int = Field(default=1024, alias="BEDROCK_EMBEDDING_DIMENSION")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/polymarket_agents",
        alias="DATABASE_URL",
    )

    polymarket_gamma_base_url: str = Field(
        default="https://gamma-api.polymarket.com",
        alias="POLYMARKET_GAMMA_BASE_URL",
    )
    polymarket_data_base_url: str = Field(
        default="https://data-api.polymarket.com",
        alias="POLYMARKET_DATA_BASE_URL",
    )
    polymarket_clob_base_url: str = Field(
        default="https://clob.polymarket.com",
        alias="POLYMARKET_CLOB_BASE_URL",
    )

    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_user: str | None = Field(default=None, alias="NEO4J_USER")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    http_timeout_seconds: float = 30.0
    http_max_retries: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
