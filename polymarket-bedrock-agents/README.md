# Polymarket Bedrock Multi-Agent

Production-oriented Python service that ingests **Polymarket** discovery data from the **Gamma API**, enriches it with **Amazon Bedrock** (embeddings + entity extraction + optional relationship reasoning), stores a **PostgreSQL + pgvector** graph, and exposes **FastAPI** endpoints to query related prediction markets.

**Recommended workflow:** treat **events** as the primary unit — record **live event counts** in snapshots, persist **events only** (nested markets are summarised in JSON, not as rows in `markets`), then run **`EventRelationshipAgent`** to find links such as **temporal containment** or **scope containment** (e.g. parent event vs child). A legacy **market-level** ingest path remains for experiments.

## What it does

- Discovers active events and markets via `https://gamma-api.polymarket.com`.
- **Event mode:** `POST /events/live-snapshot` stores **only `events`** + a row in **`event_count_snapshots`** (event count + total nested markets seen in Gamma); market titles/ids are embedded in `events.payload` for analysis **without** writing the `markets` table.
- **Event–event links:** `POST /events/relationships/detect` embeds events and runs **`EventRelationshipAgent`** (rules + optional Bedrock) into **`event_relationships`** (e.g. containment, overlap, same topic).
- Optionally reads live microstructure from `https://clob.polymarket.com` (public endpoints only; **no trading**).
- Optionally wraps `https://data-api.polymarket.com` for analytics (MVP stubs with TODOs).
- **Market mode (legacy):** market-level relationships, entities, and `/markets/...` APIs.
- Answers REST queries: `/events/...`, `/markets/...`, `/markets/search`, `/query`.

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
   ├─► RelationshipDetectionAgent ────► rules + cosine + optional Bedrock (market pairs)
   │
   ├─► EventRelationshipAgent ───────► rules + event embeddings + optional Bedrock (event pairs)
   │
   ├─► LivePriceAgent ────────────────► PolymarketClobClient
   ├─► MarketAnalyticsAgent ──────────► PolymarketDataClient (optional)
   │
   └─► GraphStorageAgent ─────────────► PostgreSQL (events, snapshots, event_edges, markets optional)
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
| **RelationshipDetectionAgent** | Bucketed candidate generation + weighted score + optional LLM for **market** pairs. |
| **EventRelationshipAgent** | **Event–event** candidates (tags, series, dates, nested market text, embeddings) + optional LLM (containment / overlap / topic). |
| **GraphStorageAgent** | Upserts events, optional markets, embeddings, entity rows, **event snapshots**, **event_relationships**, market **relationships**. |
| **QueryAnsweringAgent** | Reads stored edges + text search for evidence-first responses. |

## Prerequisites

- **Python 3.11+** (3.12 is fine).
- **Docker** (for local Postgres + pgvector), or your own Postgres with the `vector` extension.
- An **AWS account** with **Amazon Bedrock** enabled in a region that offers your chosen models.
- **Network** access from your laptop to Polymarket (`gamma-api`, `clob`, `data-api`) and to Bedrock (public internet or VPC endpoint).

---

## How to use (end-to-end)

1. **Configure AWS + Bedrock** (IAM, models, optional VPC endpoint) — see [AWS step-by-step setup](#aws-step-by-step-setup-bedrock-iam-models-vpc-embeddings).
2. **Run Postgres + API locally** — see [Run on your local machine](#run-on-your-local-machine).  
   If the database was created **before** the event-layer tables existed, apply **`app/db/migrations/002_event_focus.sql`** once (or re-init from the latest `app/db/schema.sql`).
3. **Event-centric (recommended):** snapshot live Gamma events → detect **event–event** links → query related events — see [API workflow](#api-workflow).
4. **Market-centric (legacy):** `POST /ingest/active-markets` (writes **every** market row) → `POST /relationships/detect` → `GET /markets/{id}/related`.

Open **interactive docs** after the server starts: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## AWS step-by-step setup (Bedrock, IAM, models, VPC, embeddings)

Official reference (models + IAM + Marketplace): [Request access to models](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).  
Announcement on simplified / automatic serverless model access: [Amazon Bedrock simplifies access…](https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-automatic-enablement-serverless-foundation-models/).

### Important: the old “Model access” console page is retired

AWS **retired the standalone Bedrock “Model access”** workflow in favour of:

- **Automatic enablement** of serverless foundation models (governed by **IAM** and, where applicable, **AWS Marketplace** subscription on first use).
- **Anthropic models:** a **one-time “first time use” (FTU)** use-case submission per account or organization (console or `PutUseCaseForModelAccess` API).
- **Many third-party models:** the **first successful invoke** can start a Marketplace subscription in the background (can take **up to ~15 minutes**; you may see transient errors until it completes).

You no longer wait for a single “Model access = Approved” toggle for most models; instead follow the steps below.

---

### Part A — Pick a Region (must match the app)

1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/).
2. In the **top navigation bar**, open the **Region** dropdown.
3. Choose a **commercial** Region where Bedrock offers the models you want (this repo defaults to **`us-east-1`**).
4. Write down the Region code (e.g. `us-east-1`). You will use the **same** value for `AWS_REGION` in `.env`.

---

### Part B — Account prerequisites (billing & Marketplace)

1. In the console, open **Billing and Cost Management** → **Payment methods**.
2. Ensure the account has a **valid default payment method** (required for many Marketplace-backed model flows).
3. (Optional but recommended) Open **AWS Marketplace** → **Your subscriptions** and confirm you can view subscriptions (helps debug `AccessDeniedException` during first model use).

---

### Part C — Anthropic “first time use” (only if you use Claude in `BEDROCK_REASONING_MODEL_ID`)

Skip this part if your reasoning model is **not** Anthropic.

1. In the console, open **Amazon Bedrock** (same Region as above).
2. Open **Model catalog** (or **Overview** → link to catalog, depending on console layout).
3. Search for your Claude model (e.g. **Claude 3.5 Sonnet**).
4. Open the model detail page and complete the **use case / first-time customer** form when prompted (wording varies; AWS documents this as **PutUseCaseForModelAccess** for API-driven flows).
5. Submit the form once per **account** (or once at the **organization management account** for all member accounts, per AWS docs).

---

### Part D — “Turn on” models by using the catalog or playground (console)

You do **not** rely on the retired Model access page. Instead:

1. Open **Amazon Bedrock** in your chosen Region.
2. Open **Model catalog**.
3. Select your **embedding** model (e.g. **Amazon Titan Text Embeddings v2**) and open it in **Playground** (or invoke later via this app).  
4. Select your **reasoning** model (e.g. **Claude 3.5 Sonnet**) and open **Playground** once if you want the console to walk through any remaining acceptance prompts.

If an invoke fails with Marketplace or subscription errors, wait a few minutes and retry after IAM (next part) is correct.

---

### Part E — IAM: create a policy (Bedrock invoke + Marketplace subscription)

This app calls **`bedrock-runtime`** (`InvokeModel`). For **Marketplace-listed** serverless models, AWS documents that the **first** auto-enablement often requires **`aws-marketplace:Subscribe`** (and related read actions) on the principal that performs the first subscription.

#### Step E.1 — Open the IAM policy editor

1. Open **IAM** in the console.
2. In the left sidebar, click **Policies**.
3. Click **Create policy**.
4. Click the **JSON** tab (skip the visual “Add permissions” wizard for this template).

#### Step E.2 — Paste a policy document

Use **one** of the following.

**Option 1 — Broad developer policy (simplest; least restrictive)**

Replace `REGION` with your Region (e.g. `us-east-1`). Use only in sandboxes you control.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MarketplaceSubscriptionsForBedrockModels",
      "Effect": "Allow",
      "Action": [
        "aws-marketplace:Subscribe",
        "aws-marketplace:Unsubscribe",
        "aws-marketplace:ViewSubscriptions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BedrockInvokeFoundationModels",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:REGION::foundation-model/*"
    }
  ]
}
```

**Option 2 — Tighter policy (recommended for teams)**

- Keep `bedrock:InvokeModel` resources scoped to specific foundation model ARNs, for example:

  `arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0`  
  `arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0`

- Optionally scope `aws-marketplace:Subscribe` with `aws-marketplace:ProductId` **condition keys** to specific product IDs (see AWS table in [model access guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)).

#### Step E.3 — Name and create the policy

1. Click **Next**.
2. Under **Policy name**, enter something like `PolymarketBedrockAppPolicy`.
3. Click **Create policy**.

---

### Part F — IAM: attach the policy to **your** developer identity

Pick **one** path.

#### Path F.A — Attach to an IAM **User** (common for laptops)

1. Open **IAM** → **Users**.
2. Click your username (or **Create user** if you are building a dedicated dev user).
3. Open the **Permissions** tab.
4. Click **Add permissions** → **Attach policies directly**.
5. Search for `PolymarketBedrockAppPolicy`, select it, click **Next**, then **Add permissions**.

#### Path F.B — Attach to an IAM **Role** (common for EC2/ECS/Lambda)

1. Open **IAM** → **Roles** → select the role your workload assumes.
2. **Add permissions** → **Attach policies** → attach `PolymarketBedrockAppPolicy`.

---

### Part G — Credentials on your laptop (choose one)

| Goal | Steps |
|------|--------|
| **Access keys** | IAM → **Users** → your user → **Security credentials** → **Create access key** (type: CLI/local code). Put `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` into `.env`. **Never commit `.env`.** |
| **AWS CLI profiles** | Install AWS CLI v2, run `aws configure --profile myprofile`, then export `AWS_PROFILE=myprofile` in the shell before `uvicorn`. You can leave the key fields blank in `.env`. |
| **AWS SSO** | Configure SSO (`aws configure sso`), run `aws sso login`, export `AWS_PROFILE=...`. |

This application uses **boto3** and the [default credential chain](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).

---

### Part H — Map models and embedding size into `.env`

1. Copy `.env.example` to `.env` (if you have not already).
2. Set:

```env
AWS_REGION=us-east-1

# Chat model (entity extraction + relationship LLM step)
BEDROCK_REASONING_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0

# Embedding model (market text → vector stored in pgvector)
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# Titan v2 supports 256 / 512 / 1024 — must match Postgres vector column
BEDROCK_EMBEDDING_DIMENSION=1024
```

3. **Database alignment:** `app/db/schema.sql` uses `VECTOR(1024)`. If you change `BEDROCK_EMBEDDING_DIMENSION`, update the SQL column to the same size (or recreate the table).

---

### Part I — Optional VPC interface endpoint for `bedrock-runtime` (private networks)

Use this when your app runs **inside a VPC** without a NAT path to the public Bedrock endpoint.

1. Open **VPC** → **Endpoints** → **Create endpoint**.
2. **Name tag:** e.g. `bedrock-runtime-endpoint`.
3. **Service category:** **AWS services**.
4. In the search box, type **`bedrock-runtime`** and select the service name shaped like **`com.amazonaws.<region>.bedrock-runtime`**.
5. **VPC:** choose the VPC where your workload runs.
6. **Subnets:** choose **one subnet per Availability Zone** you use (interface endpoints create ENIs per subnet).
7. **Security group:** create or select a group that **allows inbound TCP 443** from your application instances/tasks (and **outbound** as required by your org). The ENIs for the endpoint use this SG.
8. **Enable Private DNS name for this endpoint:**  
   - **Enabled (typical):** the standard Bedrock Runtime hostname for the Region resolves privately; you can leave `AWS_BEDROCK_RUNTIME_ENDPOINT_URL` **empty** in `.env`.  
   - **Disabled:** copy the **DNS name** shown for the endpoint and set:

     ```env
     AWS_BEDROCK_RUNTIME_ENDPOINT_URL=https://<endpoint-dns-name-from-console>
     ```

9. Click **Create endpoint** and wait until the status is **Available**.

For **local development on your home laptop**, you usually **skip** this part and use the public endpoint with an empty `AWS_BEDROCK_RUNTIME_ENDPOINT_URL`.

---

### Part J — Smoke-test Bedrock from your machine (optional)

With AWS CLI v2 configured for the same account/region:

```bash
aws sts get-caller-identity
aws bedrock list-foundation-models --region "$AWS_REGION" --query "modelSummaries[?contains(modelId, 'titan-embed')].modelId" --output table
```

If `AccessDeniedException` persists on first model calls, re-check **Part E** (Marketplace permissions), **Part C** (Anthropic FTU), and wait a few minutes for Marketplace subscription finalization.

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

Wait until the container is healthy. The first start applies `app/db/schema.sql` (includes `CREATE EXTENSION vector`, **event snapshots**, **event embeddings**, and **event_relationships**).

If you use your own Postgres, create database `polymarket_agents`, enable `pgvector`, and run the SQL in `app/db/schema.sql` manually.

**Upgrading an older volume:** if tables `event_count_snapshots` / `event_embeddings` / `event_relationships` are missing, run:

`psql "$DATABASE_URL" -f app/db/migrations/002_event_focus.sql`

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

See [API workflow](#api-workflow). Typical **event** order: **`/events/live-snapshot`** → **`/events/relationships/detect`** → **`/events/{id}/related`**. Typical **market** order: **ingest** → **relationships/detect** → **markets/.../related**.

### Optional: run API + DB in Docker

```bash
# Ensure .env exists with AWS and model variables; compose overrides DATABASE_URL for the api service.
docker compose up -d --build
```

The `api` service listens on port **8000**. Your machine still needs valid AWS credentials inside the container (e.g. via `.env` keys or mounting `~/.aws` — adjust compose if you use profiles/SSO).

---

## API workflow

### A — Event-centric (no `markets` rows; snapshots + event–event links)

1. **Live snapshot** — pull active events from Gamma, upsert **`events` only**, record counts in **`event_count_snapshots`** (nested markets are summarised in `events.payload`, not inserted into `markets`):

```bash
curl -sS -X POST http://127.0.0.1:8000/events/live-snapshot \
  -H 'Content-Type: application/json' \
  -d '{"max_pages": 2}'
```

Response includes `event_count`, `markets_in_gamma` (total markets seen under those events), `snapshot_id`, and `captured_at`.

2. **List recent snapshots** (audit trail of “how many events existed at capture time”):

```bash
curl -sS 'http://127.0.0.1:8000/events/snapshots?limit=10'
```

3. **Detect event–event relationships** — Titan embeddings per event, then **`EventRelationshipAgent`** (rules + optional Bedrock). Replaces rows in **`event_relationships`**:

```bash
curl -sS -X POST http://127.0.0.1:8000/events/relationships/detect \
  -H 'Content-Type: application/json' \
  -d '{"max_events": 800, "max_pairs": 4000, "use_llm": true}'
```

4. **Query events related to a given event**

```bash
curl -sS 'http://127.0.0.1:8000/events/<EVENT_ID>/related'
```

Relationship types include **`EVENT_A_CONTAINS_B`** (directed: container → contained, using dates and/or nested market question coverage), **`EVENT_TEMPORAL_OVERLAP`**, **`EVENT_SAME_TOPIC`**, **`EVENT_NEAR_DUPLICATE`**, etc. (see `app/models/event_link.py`).

---

### B — Market-centric (legacy: full market rows + market graph)

1. **Ingest** active markets (Gamma → Postgres **events + every market row** + embeddings + entities):

```bash
curl -sS -X POST localhost:8000/ingest/active-markets \
  -H 'Content-Type: application/json' \
  -d '{"max_pages": 1, "max_markets": 80, "run_relationships": false}'
```

2. **Detect market–market relationships** (replaces `relationships` table):

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

- **Event “containment”** is approximated (dates, tag/series overlap, nested market **question text** in payload, embeddings, LLM). It is not a formal proof of set inclusion on Polymarket’s internal IDs.
- The **`markets`** table and market-level graph remain for **legacy** workflows; **event mode** does not require populating `markets`.
- AWS console labels and flows change; if any step here diverges from what you see, follow the latest **[Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html)** (especially [model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)).
- Gamma / Data / CLOB paths may evolve; uncertain areas are isolated with **TODO** comments in clients.
- `GET /prices-history` parameters are best-effort; confirm against current Polymarket docs.
- Relationship LLM calls cost money; the detector only invokes Bedrock for **high composite-score** candidate pairs.
- Neo4j dual-write is stubbed (`GraphStorageAgent.neo4j_dual_write`).
- Full **Bedrock Agents** service setup (IAM, action groups) is not automated here.

## Future improvements

- Wire **Amazon Bedrock Agents** with action groups pointing to these FastAPI tools.
- Richer **event** ontology (strict partial orders, official Polymarket series/slug joins) and UI for snapshot diffs.
- Version 2: deeper **CLOB** integration (historical series alignment for `PRICE_CORRELATED`).
- Version 3: **Data API** holder / flow / OI features for behavioural relationship signals.
- Incremental ingestion schedules (EventBridge + Lambda) and idempotent checkpoints.

## Tests

```bash
pytest -q
```
