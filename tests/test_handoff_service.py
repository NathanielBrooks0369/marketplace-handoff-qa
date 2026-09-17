from typing import Any

from marketplace_qa.handoff_service import MarketplaceQA, QuestionRequest


class StubSearchClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.2, 0.8] for _ in texts]

    def query(
        self,
        collection: str,
        embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, Any],
    ) -> dict[str, Any]:
        assert metadata_filter == {"order_id": "ord-42"}
        return {
            "matches": [
                {"metadata": {"document_id": "asset-7", "order_id": "ord-42", "kind": "seller_asset", "text": "Logo files are in the shared delivery folder."}},
                {"metadata": {"document_id": "buyer-3", "order_id": "ord-42", "kind": "buyer_update", "text": "Buyer approved the final blue treatment."}},
                {"metadata": {"document_id": "handoff-9", "order_id": "ord-42", "kind": "order_handoff", "text": "Deliver SVG and PNG exports by Friday."}},
                {"metadata": {"document_id": "other-1", "order_id": "ord-99", "kind": "order_handoff", "text": "Unrelated order."}},
            ]
        }

    def rerank(self, query: str, candidates: list[str], top_k: int) -> dict[str, Any]:
        assert "Unrelated order." not in candidates
        return {"results": [{"index": 2}, {"index": 1}]}


def test_answer_is_scoped_and_marks_complete_handoff() -> None:
    result = MarketplaceQA(StubSearchClient()).answer(
        QuestionRequest(
            collection="marketplace-docs",
            order_id="ord-42",
            question="What should we deliver and when?",
            top_k=2,
        )
    )

    assert result.handoff_ready is True
    assert result.answer.startswith("Deliver SVG and PNG exports by Friday.")
    assert [citation.document_id for citation in result.citations] == ["handoff-9", "buyer-3"]
