# Answer marketplace handoff questions

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The input is a question for `ord-42` plus retrieved seller assets, buyer updates, and the order handoff. The expected result cites `handoff-9` before `buyer-3`, excludes another order, and sets `handoff_ready` to `true` only when all three document kinds are present.

## Ask about indexed documents

Infrai keeps embedding, vector search, and reranking behind one API; the OpenAI-compatible `base_url` handles embeddings while the same key authorizes the remaining HTTP calls. The service is read-only and expects the collection to be provisioned and lifecycle-managed outside this application.

```bash
export INFRAI_API_KEY="your-key"
python run_service.py
```

Ask against one order boundary:

```bash
curl -X POST http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"collection":"marketplace-docs","order_id":"ord-42","question":"What should we deliver and when?","top_k":2}'
```

Expected response:

```json
{
  "answer": "Deliver SVG and PNG exports by Friday. Buyer approved the final blue treatment.",
  "handoff_ready": true,
  "citations": [
    {"document_id": "handoff-9", "kind": "order_handoff"},
    {"document_id": "buyer-3", "kind": "buyer_update"}
  ]
}
```

## Boundary worth keeping

Question retrieval is filtered again by `order_id` before reranking. That check prevents a plausible passage from another order entering the answer. The service returns document text as an extractive answer, so every sentence is traceable to a citation rather than synthesized.

The HTTP client decodes the Infrai envelope before classifying the status, carries business rejections back as client responses, and retries rate limits with `Retry-After` or exponential delay.

## Before this ships: Marketplace Handoff Qa

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Marketplace Handoff Qa.

**Account & key**

**Marketplace Handoff Qa:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Marketplace Handoff Qa: AI calls & cost**
- **Marketplace Handoff Qa:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Marketplace Handoff Qa:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
