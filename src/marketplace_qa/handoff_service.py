from __future__ import annotations

from typing import Any, Literal, Protocol

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # Keep core decision logic importable for lightweight clients.
    class BaseModel:
        def __init__(self, **data: Any) -> None:
            for name, value in data.items():
                setattr(self, name, value)

    def Field(default: Any = ..., **_: Any) -> Any:
        return default

    class Request:  # pragma: no cover - only a type placeholder without web dependencies
        pass

    class JSONResponse:
        def __init__(self, *, status_code: int, content: Any) -> None:
            self.status_code = status_code
            self.content = content

    class FastAPI:
        def __init__(self, **_: Any) -> None:
            self.routes: list[Any] = []

        def exception_handler(self, *_: Any, **__: Any) -> Any:
            return lambda function: function

        def post(self, *_: Any, **__: Any) -> Any:
            return lambda function: function

try:
    from .infrai_client import InfraiClient, InfraiError
except ModuleNotFoundError:  # Client dependencies are only needed when starting the HTTP service.
    class InfraiError(Exception):
        status_code = 502
        detail: dict[str, Any] = {}

    class InfraiClient:
        def __init__(self, *_: Any, **__: Any) -> None:
            raise RuntimeError("Install the project dependencies before starting the service")


DocumentKind = Literal["seller_asset", "buyer_update", "order_handoff"]


class QuestionRequest(BaseModel):
    collection: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


class Citation(BaseModel):
    document_id: str
    kind: DocumentKind


class AnswerResult(BaseModel):
    answer: str
    handoff_ready: bool
    citations: list[Citation]


class SearchClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        pass

    def query(
        self,
        collection: str,
        embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, Any],
    ) -> dict[str, Any]:
        pass

    def rerank(
        self, query: str, candidates: list[str], top_k: int
    ) -> dict[str, Any]:
        pass


class MarketplaceQA:
    def __init__(self, client: SearchClient) -> None:
        self.client = client

    def answer(self, request: QuestionRequest) -> AnswerResult:
        query_embedding = self.client.embed([request.question])[0]
        result = self.client.query(
            request.collection,
            query_embedding,
            request.top_k * 2,
            {"order_id": request.order_id},
        )
        matches = [
            match
            for match in result.get("matches", [])
            if match.get("metadata", {}).get("order_id") == request.order_id
        ]
        if not matches:
            return AnswerResult(
                answer="No indexed document answers this order question.",
                handoff_ready=False,
                citations=[],
            )

        candidates = [str(match["metadata"]["text"]) for match in matches]
        ranked = self.client.rerank(request.question, candidates, request.top_k)
        selected = self._selected_matches(matches, ranked)
        kinds = {match["metadata"]["kind"] for match in matches}
        return AnswerResult(
            answer=" ".join(str(match["metadata"]["text"]) for match in selected),
            handoff_ready={"seller_asset", "buyer_update", "order_handoff"}.issubset(kinds),
            citations=[
                Citation(
                    document_id=str(match["metadata"]["document_id"]),
                    kind=match["metadata"]["kind"],
                )
                for match in selected
            ],
        )

    @staticmethod
    def _selected_matches(
        matches: list[dict[str, Any]], ranked: dict[str, Any]
    ) -> list[dict[str, Any]]:
        results = ranked.get("results", [])
        indexes = [item.get("index") for item in results]
        selected = [matches[index] for index in indexes if isinstance(index, int) and index < len(matches)]
        return selected or matches[:1]


def create_app(client: SearchClient | None = None) -> FastAPI:
    app = FastAPI(title="Marketplace handoff QA")
    workflow = MarketplaceQA(client or InfraiClient())

    @app.exception_handler(InfraiError)
    async def infrai_error_handler(_: Request, exc: InfraiError) -> JSONResponse:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        return JSONResponse(status_code=status, content={"error": exc.detail})

    @app.post("/questions", response_model=AnswerResult)
    def answer_question(request: QuestionRequest) -> AnswerResult:
        return workflow.answer(request)

    return app
