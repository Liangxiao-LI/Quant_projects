"""Compute and normalise text embeddings via Bedrock."""

from app.config import Settings, get_settings
from app.services.bedrock_client import BedrockClient


class EmbeddingService:
    def __init__(
        self,
        bedrock: BedrockClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._bedrock = bedrock or BedrockClient(settings=settings or get_settings())

    def embed(self, text: str) -> list[float]:
        cleaned = (text or "").strip()
        if not cleaned:
            dim = get_settings().bedrock_embedding_dimension
            return [0.0] * dim
        return self._bedrock.invoke_embedding(cleaned)
