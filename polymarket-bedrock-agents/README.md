# Polymarket Bedrock Multi-Agent

Production-oriented Python service that ingests **Polymarket** discovery data from the **Gamma API**, enriches it with **Amazon Bedrock** (embeddings + entity extraction + optional relationship reasoning), stores a **PostgreSQL + pgvector** graph, and exposes **FastAPI** endpoints to query related prediction markets.

## What it does

- Discovers active events and markets via `https://gamma-api.polymarket.com`.
- Optionally reads live microstructure from `https://clob.polymarket.com` (public endpoints only; **no trading**).
- Optionally wraps `https://data-api.polymarket.com` for analytics (MVP stubs with TODOs).
- Detects relationships (shared entities/tags, series/event grouping, embeddings, optional LLM refinement, optional price correlation hook).
- Answers REST queries such as `/markets/{id}/related` and `/markets/search`.

## Architecture (text diagram)

```
User / CLI
   │
   ▼
FastAPI (routes)
   │
   ├─► SupervisorAgent ─────────────► QueryAnsweringAgent
   │
   ├─► MarketDataIngestionAgent ─────► PolymarketGammaClient
   │
   ├─► EntityExtractionAgent ─────────► BedrockClient (LLM JSON)
   ├─► EmbeddingService ──────────────► BedrockClient (vectors)
   │
   ├─► RelationshipDetectionAgent ────► rules + cosine + optional Bedrock classify
   │
   ├─► LivePriceAgent ────────────────► PolymarketClobClient
   ├─► MarketAnalyticsAgent ──────────► PolymarketDataClient (optional)
   │
   └─► GraphStorageAgent ─────────────► PostgreSQL (+ optional Neo4j hook later)
```

> **Bedrock Agents vs Runtime:** this MVP orchestrates agents in Python (clear boundaries, easy tests). You can later register the same tools with the **Bedrock Agents** control plane; the clients and scoring logic carry over unchanged.

## Agents (roles)

| Agent | Responsibility |
|-------|------------------|
| **SupervisorAgent** | Cheap NL routing for `/query` (search vs hints). |
| **MarketDataIngestionAgent** | Paginates Gamma `/events?active=true&closed=false`, normalises nested markets. |
| **LivePriceAgent** | Parallel CLOB reads (`/price`, `/midpoint`, `/spread`, `/book`). |
| **MarketAnalyticsAgent** | Data API façade (TODOs on exact paths). |
| **EntityExtractionAgent** | Bedrock LLM → structured `Entity` JSON. |
| **RelationshipDetectionAgent** | Bucketed candidate generation + weighted score + optional LLM for high-score pairs only. |
| **GraphStorageAgent** | Upserts SQL rows for markets, embeddings, entities, relationships. |
| **QueryAnsweringAgent** | Reads stored edges + text search for evidence-first responses. |

## Local run

### 1. Start Postgres (pgvector)

```bash
cd polymarket-bedrock-agents
cp .env.example .env
docker compose up -d db
```

### 2. Python environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=.
uvicorn app.main:app --reload
```

### 3. AWS Bedrock configuration

1. Enable the chosen models in your AWS account (same region as `AWS_REGION`).
2. Populate `.env`:

```env
AWS_REGION=us-east-1
BEDROCK_REASONING_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_EMBEDDING_DIMENSION=1024
```

3. Provide credentials via standard AWS mechanisms (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, SSO, or instance role).

> **Vector dimension:** `app/db/schema.sql` fixes `VECTOR(1024)`. If you switch embedding models, update both SQL and `BEDROCK_EMBEDDING_DIMENSION`.

## API workflow

1. **Ingest** active markets (Gamma → Postgres + embeddings + entities):

```bash
curl -sS -X POST localhost:8000/ingest/active-markets \
  -H 'Content-Type: application/json' \
  -d '{"max_markets": 80, "run_relationships": false}'
```

2. **Detect relationships** (uses stored embeddings/entities; replaces `relationships` table):

```bash
curl -sS -X POST localhost:8000/relationships/detect \
  -H 'Content-Type: application/json' \
  -d '{"use_llm": true, "limit_pairs": 5000}'
```

3. **Query related markets**

```bash
curl -sS localhost:8000/markets/<MARKET_ID>/related
```

4. **Keyword search**

```bash
curl -sS 'localhost:8000/markets/search?q=bitcoin'
```

5. **Natural language (MVP routing)**

```bash
curl -sS -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"find markets about trump"}'
```

## Limitations

- Gamma / Data / CLOB paths may evolve; uncertain areas are isolated with **TODO** comments in clients.
- `GET /prices-history` parameters are best-effort; confirm against current Polymarket docs.
- Relationship LLM calls cost money; the detector only invokes Bedrock for **high composite-score** candidate pairs.
- Neo4j dual-write is stubbed (`GraphStorageAgent.neo4j_dual_write`).
- Full **Bedrock Agents** service setup (IAM, action groups) is not automated here.

## Future improvements

- Wire **Amazon Bedrock Agents** with action groups pointing to these FastAPI tools.
- Version 2: deeper **CLOB** integration (historical series alignment for `PRICE_CORRELATED`).
- Version 3: **Data API** holder / flow / OI features for behavioural relationship signals.
- Incremental ingestion schedules (EventBridge + Lambda) and idempotent checkpoints.

## Tests

```bash
pytest -q
```
