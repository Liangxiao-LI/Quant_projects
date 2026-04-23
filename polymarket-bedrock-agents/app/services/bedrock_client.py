"""AWS Bedrock Runtime wrapper for reasoning and embeddings (no Agents control plane in MVP)."""

import json
from typing import Any

import boto3
from botocore.config import Config

from app.config import Settings, get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BedrockClient:
    """
    Invokes foundation models on Amazon Bedrock.
    Model IDs come from environment; supports common Anthropic Messages and Titan embedding bodies.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        session_kw: dict[str, Any] = {"region_name": self._settings.aws_region}
        if self._settings.aws_access_key_id and self._settings.aws_secret_access_key:
            session_kw["aws_access_key_id"] = self._settings.aws_access_key_id
            session_kw["aws_secret_access_key"] = self._settings.aws_secret_access_key
        client_kw = dict(session_kw)
        if self._settings.aws_bedrock_runtime_endpoint_url:
            client_kw["endpoint_url"] = self._settings.aws_bedrock_runtime_endpoint_url
        self._client = boto3.client(
            "bedrock-runtime",
            config=Config(retries={"max_attempts": 5, "mode": "adaptive"}),
            **client_kw,
        )

    def invoke_reasoning(self, system: str, user: str, *, max_tokens: int = 2048) -> str:
        model_id = self._settings.bedrock_reasoning_model_id
        if model_id.startswith("anthropic."):
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
        else:
            # Converse-style / other providers: TODO extend for amazon.nova-* etc.
            body = {
                "messages": [
                    {"role": "system", "content": [{"text": system}]},
                    {"role": "user", "content": [{"text": user}]},
                ],
                "inferenceConfig": {"maxTokens": max_tokens},
            }
        resp = self._client.invoke_model(
            modelId=model_id,
            body=json.dumps(body).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(resp["body"].read())
        if model_id.startswith("anthropic."):
            parts = payload.get("content") or []
            texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
            return "\n".join(texts).strip()
        output = payload.get("output", {}).get("message", {}).get("content", [])
        texts = [c.get("text", "") for c in output if isinstance(c, dict)]
        return "\n".join(texts).strip()

    def invoke_embedding(self, text: str) -> list[float]:
        model_id = self._settings.bedrock_embedding_model_id
        if "titan-embed" in model_id.lower():
            body = {"inputText": text}
            if "v2" in model_id.lower():
                body["dimensions"] = self._settings.bedrock_embedding_dimension
                body["normalize"] = True
        else:
            # TODO: Cohere / other embedding providers on Bedrock
            body = {"inputText": text}
        resp = self._client.invoke_model(
            modelId=model_id,
            body=json.dumps(body).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(resp["body"].read())
        if "embedding" in payload:
            vec = payload["embedding"]
        elif "embeddingsByType" in payload:
            vec = payload["embeddingsByType"]["float"][0]
        else:
            vec = []
        if not isinstance(vec, list):
            raise ValueError("unexpected_embedding_shape")
        dim = self._settings.bedrock_embedding_dimension
        if len(vec) > dim:
            vec = vec[:dim]
        elif len(vec) < dim:
            vec = vec + [0.0] * (dim - len(vec))
        return [float(x) for x in vec]
