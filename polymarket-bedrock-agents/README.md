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

## Prerequisites

- **Python 3.11+** (3.12 is fine).
- **Docker** (for local Postgres + pgvector), or your own Postgres with the `vector` extension.
- An **AWS account** with **Amazon Bedrock** enabled in a region that offers your chosen models.
- **Network** access from your laptop to Polymarket (`gamma-api`, `clob`, `data-api`) and to Bedrock (public internet or VPC endpoint).

---

## How to use (end-to-end)

1. **Configure AWS + Bedrock** (IAM, model access, optional VPC endpoint) — see [AWS Bedrock setup](#aws-bedrock-setup-iam-models-vpc-endpoint--embedding).
2. **Run Postgres + API locally** — see [Run on your local machine](#run-on-your-local-machine).
3. **Ingest** markets from Gamma (writes rows, embeddings, entities):

   `POST /ingest/active-markets` with JSON body (see [API workflow](#api-workflow)).

4. **Detect relationships** (reads DB, may call Bedrock for high-score pairs):

   `POST /relationships/detect`.

5. **Query** stored related markets or search by keyword:

   `GET /markets/{market_id}/related`, `GET /markets/search?q=...`, or `POST /query`.

Open **interactive docs** after the server starts: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## AWS Bedrock setup (IAM, models, VPC endpoint, & embedding)

### 1. Region and model access

1. In the [AWS console](https://console.aws.amazon.com/), open **Amazon Bedrock** in the region you will use (must match `AWS_REGION`, e.g. `us-east-1`).
2. Open **Model access** (or **Bedrock → Cross-region inference / Marketplace** depending on console version) and **request access** to:
   - A **chat / reasoning** model (e.g. Anthropic Claude 3.5 Sonnet), used for entity extraction and relationship classification.
   - An **embedding** model (e.g. **Amazon Titan Text Embeddings v2**), used to vectorise market text for similarity and candidate search.

Wait until access shows as **Available** before calling the API.

### 2. IAM permissions for local development

Create (or attach to your user/role) a policy that allows **Bedrock Runtime** invoke on your models, for example:

- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream` (optional, if you later stream)

Scope `resource` to the specific foundation model ARNs you enabled, or use the account-wide pattern your security team allows.

For local runs, common credential sources are:

| Method | What to set |
|--------|-------------|
| Access keys | `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env` (do not commit `.env`). |
| AWS CLI profiles | `export AWS_PROFILE=my-profile` (leave key vars empty in `.env`). |
| SSO | `aws sso login` then `AWS_PROFILE=...`. |

The app uses `boto3` and picks up the [default credential chain](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).

### 3. Wire reasoning + embedding model IDs into the app

Copy `.env.example` to `.env` and set:

```env
AWS_REGION=us-east-1

# Chat model (entity extraction + relationship LLM step)
BEDROCK_REASONING_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0

# Embedding model (market text → vector stored in pgvector)
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# Output width for Titan v2 (256 / 512 / 1024). Must match Postgres column size.
BEDROCK_EMBEDDING_DIMENSION=1024
```

**Embedding model ↔ database:** `app/db/schema.sql` defines `market_embeddings.embedding` as `VECTOR(1024)`. If you switch to another model (e.g. different dimension):

1. Change `BEDROCK_EMBEDDING_MODEL_ID` and `BEDROCK_EMBEDDING_DIMENSION` in `.env`.
2. Alter or recreate the `market_embeddings` column to the same dimension (or apply a new migration).

The code pads or truncates vectors to `BEDROCK_EMBEDDING_DIMENSION` before insert so the **configured dimension** and **SQL vector size** must agree.

### 4. Optional: VPC interface endpoint (private AWS access)

If your workload runs inside a VPC without direct internet egress, create a **VPC interface endpoint** for **Bedrock Runtime**:

1. **VPC → Endpoints → Create endpoint**.
2. Service name: search for **`bedrock-runtime`** (format like `com.amazonaws.<region>.bedrock-runtime`).
3. Choose subnets + security groups that allow your app (or bastion) to reach the endpoint on **HTTPS (443)**.
4. **Private DNS** for the endpoint:
   - **Enabled:** your app can keep using the normal regional hostname; you usually **do not** need `AWS_BEDROCK_RUNTIME_ENDPOINT_URL`.
   - **Disabled:** AWS gives you a **VPC endpoint DNS name** (and often a private hosted zone). Set that URL in `.env`:

     ```env
     AWS_BEDROCK_RUNTIME_ENDPOINT_URL=https://<your-vpce-dns-name>
     ```

The application passes this value to `boto3.client("bedrock-runtime", endpoint_url=...)`. For **local laptop** development, most users use the **default public endpoint** and leave `AWS_BEDROCK_RUNTIME_ENDPOINT_URL` empty.

---

## Run on your local machine

### 1. Clone and enter the project

```bash
cd polymarket-bedrock-agents
cp .env.example .env
# Edit .env: AWS_REGION, model IDs, optional keys / endpoint URL, DATABASE_URL if needed.
```

### 2. Start PostgreSQL (Docker Compose)

```bash
docker compose up -d db
```

Wait until the container is healthy. The first start applies `app/db/schema.sql` (includes `CREATE EXTENSION vector`).

If you use your own Postgres, create database `polymarket_agents`, enable `pgvector`, and run the SQL in `app/db/schema.sql` manually.

### 3. Python virtual environment and dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export PYTHONPATH=.
```

### 4. Start the API

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Verify

```bash
curl -sS http://127.0.0.1:8000/health
# {"status":"ok"}
```

### 6. Run the full pipeline (example)

See [API workflow](#api-workflow) for `curl` examples. Typical order: **ingest** → **relationships/detect** → **markets/.../related**.

### Optional: run API + DB in Docker

```bash
# Ensure .env exists with AWS and model variables; compose overrides DATABASE_URL for the api service.
docker compose up -d --build
```

The `api` service listens on port **8000**. Your machine still needs valid AWS credentials inside the container (e.g. via `.env` keys or mounting `~/.aws` — adjust compose if you use profiles/SSO).

---

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
