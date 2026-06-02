# Investor Intelligence Pipeline

An automated investor research platform for discovering investor websites, extracting structured firm data, storing it in Postgres/Supabase, and reviewing data quality from a web dashboard.

The project is designed as a lightweight MVP: simple scheduled ingestion, searchable investor records, review workflows, enrichment tools, and operational visibility without heavy orchestration or multi-agent crawling.

## Features

- Investor discovery from generated or manual search queries
- Tavily web search integration
- Firecrawl-based page extraction, with self-hosted Firecrawl support
- LLM structured parsing with OpenAI first, then Groq/Ollama fallbacks
- Supabase/Postgres storage through SQLAlchemy models
- Investor, partner, and portfolio company tables
- Review Queue for human approval/rejection before updates
- Data Quality dashboard for missing fields and coverage gaps
- Enrichment backlog/audit tooling
- Blocklist for rejected/noisy sites
- Next.js frontend dashboard
- FastAPI backend API
- Local scheduler for recurring ingestion

## Architecture

```text
Next.js Frontend
        |
        v
FastAPI Backend
        |
        v
Supabase / Postgres

Local ingestion worker:

Query generation
        |
        v
Tavily Search
        |
        v
Firecrawl Extraction
        |
        v
LLM Structured Parsing
        |
        v
Review Queue / Database Insert
```

For development and demos, Firecrawl can run locally while the deployed frontend/backend read from the shared Supabase database.

## Tech Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- Postgres / Supabase
- Tavily
- Firecrawl
- OpenAI / Groq / Ollama fallback parsing
- APScheduler / lightweight scheduler scripts

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- Recharts
- Lucide icons

### Database

- Supabase Postgres
- pgvector optional for semantic search

## Repository Structure

```text
.
├── app/
│   ├── api/                  # FastAPI routers
│   ├── config/               # Settings, taxonomy, query universe
│   ├── database/             # SQLAlchemy DB/session/models
│   ├── extraction/           # Firecrawl extraction helpers
│   ├── parsing/              # LLM structured parsing
│   ├── query/                # Query generation/expansion
│   ├── relevance/            # Search result relevance classification
│   ├── search/               # Tavily + semantic search
│   └── utils/                # Deduplication, normalization, repair helpers
├── frontend/                 # Next.js app
├── raw_markdown/             # Extracted markdown output
├── parsed_json/              # Parsed investor JSON output
├── exports/                  # Audit/backlog/export files
├── main.py                   # FastAPI entrypoint
├── run_pipeline.py           # Search + extraction pipeline
├── parse_markdown.py         # Parse markdown into structured JSON
├── insert_into_db.py         # Upsert parsed JSON into DB
├── scheduler.py              # Local recurring scheduler
├── audit_investor_coverage.py
├── build_enrichment_backlog.py
└── enrich_investor_backlog.py
```

## Requirements

- Python 3.11+
- Node.js 18+
- Postgres database or Supabase project
- Tavily API key
- OpenAI or Groq API key
- Firecrawl Cloud key or local self-hosted Firecrawl

## Backend Setup

Create and activate a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root.

Recommended Supabase connection style:

```env
DATABASE_URL=postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-xxx.pooler.supabase.com:5432/postgres
```

Alternative individual DB fields:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=investor_intelligence
DB_USER=postgres
DB_PASSWORD=your_password
```

Required API/config values:

```env
TAVILY_API_KEY=your_tavily_key
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
ADMIN_API_KEY=change_this_for_admin_actions
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Firecrawl options:

```env
# Self-hosted local Firecrawl
FIRECRAWL_API_URL=http://localhost:3002

# Or Firecrawl Cloud
FIRECRAWL_API_KEY=your_firecrawl_cloud_key
```

Pipeline limits:

```env
TEST_MODE=true
TEST_QUERY_LIMIT=10
TEST_URL_LIMIT=5
MAX_TOTAL_URLS=500
RECRAWL_AFTER_DAYS=30
FIRECRAWL_TIMEOUT_SECONDS=45
```

Use `TEST_MODE=true` while validating against a live database.

## Database Setup

Create tables:

```powershell
python create_tables.py
```

For an existing database, run migrations carefully:

```powershell
python migrate_pipeline_tables.py
```

Before running migrations against a shared/production database, take a Supabase backup or snapshot.

## Running The Backend Locally

```powershell
.\.venv\Scripts\activate
uvicorn main:app --reload
```

Useful local URLs:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/api/metrics
http://127.0.0.1:8000/docs
```

## Frontend Setup

```powershell
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_ADMIN_API_KEY=your_admin_key_if_using_admin_buttons
```

Run the frontend:

```powershell
npm run dev
```

Open:

```text
http://localhost:3000
```

## Running Firecrawl Locally

Firecrawl is optional for viewing data, but required for extraction/manual ingestion/enrichment.

```powershell
cd C:\Users\crade\Desktop\firecrawl
docker compose up --build
```

Test Firecrawl:

```powershell
curl.exe -X POST http://localhost:3002/v1/scrape -H "Content-Type: application/json" -d "{\"url\":\"https://example.com\",\"formats\":[\"markdown\"]}"
```

Expected response includes:

```json
"success": true
```

Then make sure the backend `.env` contains:

```env
FIRECRAWL_API_URL=http://localhost:3002
```

## Running The Pipeline

Run a single query:

```powershell
python run_pipeline.py "Voice AI Seed venture capital firm portfolio"
python parse_markdown.py
python insert_into_db.py
```

Run the local scheduler:

```powershell
python scheduler.py
```

The local scheduler writes to whichever database your `.env` points to. If your `.env` uses Supabase, the deployed website will update after records are inserted.

## Enrichment And Data Quality

Audit current coverage:

```powershell
python audit_investor_coverage.py
```

Build enrichment backlog:

```powershell
python build_enrichment_backlog.py
```

Run enrichment batch:

```powershell
python enrich_investor_backlog.py exports/investor_enrichment_backlog.json exports/investor_enrichment_results.json 10
```

Enrichment results are queued for review instead of directly updating investor records.

## Review Workflow

The Review Queue is used to prevent bad records from being written automatically.

Typical flow:

```text
Extraction/parsing result
        |
        v
Review Queue
        |
        | approve
        v
Insert/update investor DB

        |
        | reject
        v
Block site / ignore noisy source
```

Rejected sites can be blocklisted so future searches do not keep surfacing the same low-quality sources.

## API Overview

Common endpoints:

```text
GET  /health
GET  /api/metrics
GET  /api/dashboard/distributions
GET  /api/investors
GET  /api/investors/{id}
GET  /api/partners
GET  /api/portfolio-companies
GET  /api/quality/coverage
GET  /api/review-queue
GET  /api/blocklist
POST /api/queries/preview
POST /api/pipeline/runs
POST /api/manual-ingestion/url
POST /api/review-queue/{id}/approve
POST /api/review-queue/{id}/reject
```

Admin/protected actions use:

```text
x-admin-key: YOUR_ADMIN_API_KEY
```

For a public demo, avoid exposing destructive/admin workflows broadly. `NEXT_PUBLIC_ADMIN_API_KEY` is visible in the browser and should not be treated as production-grade security.

## Deployment For Demo/Showcase

Recommended simple deployment:

```text
Frontend: Vercel
Backend: Render
Database: Supabase
Firecrawl: local development only
```

This means:

- The deployed website can display/search existing Supabase data.
- You can run ingestion locally with Firecrawl.
- Local ingestion writes to Supabase.
- The deployed website updates because it reads Supabase.
- Deployed scraping/manual extraction may not work unless Firecrawl is hosted publicly.

### Render Backend

Render settings:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
```

Render environment variables:

```env
DATABASE_URL=your_supabase_connection_string
TAVILY_API_KEY=your_tavily_key
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
ADMIN_API_KEY=your_admin_key
CORS_ORIGINS=https://your-vercel-app.vercel.app
ENABLE_COMPAT_ROUTES=true
```

For a read-only demo, omit `FIRECRAWL_API_URL` on Render.

Test Render:

```text
https://your-render-service.onrender.com/health
https://your-render-service.onrender.com/api/metrics
```

### Vercel Frontend

Vercel settings:

```text
Root Directory: frontend
Framework: Next.js
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

Vercel environment variables:

```env
API_BASE_URL=https://your-render-service.onrender.com
NEXT_PUBLIC_API_BASE_URL=https://your-render-service.onrender.com
NEXT_PUBLIC_ADMIN_API_KEY=your_admin_key_if_needed
```

Important:

- `API_BASE_URL` must include `https://`
- Do not add `/api` to the end
- Redeploy Vercel after env var changes
- Redeploy without build cache if values appear stale

Test Vercel API rewrite:

```text
https://your-vercel-app.vercel.app/api/metrics
```

If this returns real counts, client-side pages should load data correctly.

## Data Collaboration

For combining data from multiple local databases into one shared Supabase database, use JSON export/import instead of copying raw table IDs.

Export:

```powershell
python export_investors_json.py exports/my_investors.json
```

Import into shared DB:

```powershell
python import_investors_json.py exports/my_investors.json
```

The import path uses upsert logic and dedupes by normalized firm identity where possible.

## Development Notes

- Do not commit `.env` files.
- Keep `.env`, `frontend/.env.local`, Docker volumes, and generated caches out of Git.
- Supabase data is remote and is not affected by deleting local Docker images/volumes.
- Firecrawl local Docker state can be rebuilt if Docker is reset.
- The deployed frontend/backend can be used for browsing data while ingestion runs locally.

## Common Troubleshooting

### Vercel shows zeros but Render has data

Check:

```env
API_BASE_URL=https://your-render-service.onrender.com
NEXT_PUBLIC_API_BASE_URL=https://your-render-service.onrender.com
```

Then redeploy Vercel with build cache disabled.

### Render says no open ports detected

Use:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
```

### Render runs out of memory

Avoid loading extraction/parsing/enrichment modules at startup. For read-only demo deployments, keep Firecrawl disabled on Render and run ingestion locally.

### Firecrawl local connection refused

Start Firecrawl:

```powershell
cd C:\Users\crade\Desktop\firecrawl
docker compose up --build
```

Then verify:

```powershell
curl.exe -X POST http://localhost:3002/v1/scrape -H "Content-Type: application/json" -d "{\"url\":\"https://example.com\",\"formats\":[\"markdown\"]}"
```

### API route works on Render but not Vercel

Test Vercel rewrite:

```text
https://your-vercel-app.vercel.app/api/metrics
```

If that fails, Vercel env vars or `next.config.ts` rewrite configuration are wrong.

## Current MVP Scope

Included:

- Investor discovery
- Web search
- Extraction
- Structured parsing
- Supabase/Postgres storage
- Scheduled/local ingestion
- Review queue
- Data quality/enrichment tooling
- Searchable frontend

Not included:

- CRM replacement
- Outreach automation
- Warm intro graph
- Multi-agent orchestration
- Relationship intelligence graph
- Fully hosted Firecrawl in the demo setup

## License

This project is currently intended for internal/demo use. Add a license before distributing publicly.
