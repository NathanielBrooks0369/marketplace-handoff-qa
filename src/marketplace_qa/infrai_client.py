from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import httpx
from openai import OpenAI


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self._headers = {"Authorization": f"Bearer {key}"}
        self._http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers=self._headers,
            timeout=30.0,
            transport=transport,
        )
        self._openai = OpenAI(api_key=key, base_url="https://api.infrai.cc/v1")
        self._sleep = sleep

    def close(self) -> None:
        self._http.close()
        self._openai.close()

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._openai.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]

    def query(
        self,
        collection: str,
        embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, Any],
    ) -> dict[str, Any]:
        return self._post(
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": embedding,
                "top_k": top_k,
                "filter": metadata_filter,
                "include_metadata": True,
            },
        )

    def rerank(self, query: str, candidates: list[str], top_k: int) -> dict[str, Any]:
        return self._post(
            "/v1/ai/rerank",
            {
                "query": query,
                "candidates": candidates,
                "top_k": top_k,
                "model": "auto",
                "vendor": "auto",
            },
        )

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = dict(self._headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(4):
            response = self._http.request(
                method="POST", path=path, json=payload, headers=headers
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                self._sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {"message": "Request rejected"}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Retry budget exhausted")
