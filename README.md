# Investor Intelligence Pipeline

Lightweight automated investor research pipeline for discovering investor pages,
extracting structured firm data, and keeping a Postgres-backed investor database
up to date.

The current implementation intentionally keeps the V1 workflow simple:

```text
Query generation
  -> Tavily search
  -> Firecrawl page extraction
  -> Groq/Ollama structured parsing
  -> Postgres storage
  -> daily scheduled refresh
```

OpenAI structured outputs are planned for the final stage once API rate limits
are no longer a blocker. Tavily is the active search provider for V1.

## What V1 Includes

- Manual query input through `run_pipeline.py "<query>"`
- Generated investor discovery queries by sector, stage, geography, and theme
- Tavily search with URL deduplication
- High-signal page extraction with Firecrawl
- Structured investor parsing with Groq and Ollama fallback
- Postgres storage for investors, partners, portfolio companies, crawl history,
  crawl queue, and failed URL retries
- Daily scheduler process
- Execution logs and failed URL tracking
- Optional Streamlit dashboard for operational visibility and search

## What V1 Does Not Try To Be

- A CRM
- An outreach automation system
- A relationship intelligence graph
- A multi-agent research system
- A recursive autonomous crawler
- A required scoring or recommendation engine

Semantic search, pgvector, ranking scripts, and the dashboard are available as
optional extras in this repository. They are not required for the core ingestion
pipeline.

## Setup

Create a virtual environment and install dependencies:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

For tests:

```bash
pip install -r requirements-dev.txt
```

Configure `.env`:

```env
TAVILY_API_KEY=your_tavily_key
FIRECRAWL_API_KEY=your_firecrawl_key
GROQ_API_KEY=your_groq_key

DB_HOST=localhost
DB_PORT=5432
DB_NAME=investor_intelligence
DB_USER=postgres
DB_PASSWORD=your_password

TEST_MODE=true
TEST_QUERY_LIMIT=10
MAX_TOTAL_URLS=500
RECRAWL_AFTER_DAYS=30
FIRECRAWL_TIMEOUT_SECONDS=45
SCHEDULE_TIME=02:00
```

Use `TEST_MODE=true` while validating the pipeline against a live database. Set
`TEST_MODE=false` only after confirming the search, extraction, parsing, and
upsert behavior on a small sample.

## Database Setup

Create tables:

```bash
python create_tables.py
```

For an existing database, run the migration only after backing up or snapshotting
the database:

```bash
python migrate_pipeline_tables.py
```

The migration only adds missing columns/tables needed by the pipeline. It does
not drop existing data.

## Running The Pipeline

Run a single manual discovery query:

```bash
python run_pipeline.py "AI infrastructure seed investors"
python parse_markdown.py
python insert_into_db.py
```

Run the daily scheduler process:

```bash
python scheduler.py
```

The scheduler runs `run_pipeline.py`, `parse_markdown.py`, `insert_into_db.py`,
and failed URL retries once per day at `SCHEDULE_TIME`.

## Running The FastAPI Backend

Start the API server:

```bash
uvicorn main:app --reload
```

Open the API docs:

```text
http://127.0.0.1:8000/docs
```

Core frontend endpoints:

```text
GET  /api/health
GET  /api/investors
GET  /api/investors/{id}
GET  /api/investors/export
GET  /api/search/structured
POST /api/search/semantic
GET  /api/operations/metrics
GET  /api/operations/crawl-queue
GET  /api/operations/crawled-urls
GET  /api/operations/failed-urls
POST /api/queries/preview
POST /api/pipeline/runs
GET  /api/pipeline/runs
GET  /api/pipeline/runs/{id}
GET  /api/pipeline/runs/{id}/logs
POST /api/operations/failed-urls/{id}/retry
```

Write endpoints require an admin header:

```text
X-Admin-Key: your-admin-key
```

Set these in `.env` for the frontend/API bridge:

```env
ADMIN_API_KEY=change-me
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## Scheduling In Production

The built-in scheduler is intentionally lightweight. It must remain running. For
production, prefer one of these wrappers:

- Windows Task Scheduler running `python scheduler.py` at startup
- Linux cron running the three pipeline commands directly
- Docker container with a restart policy
- GitHub Actions or another hosted scheduled job

Example Linux cron:

```cron
0 2 * * * cd /path/to/project && /path/to/venv/bin/python run_pipeline.py && /path/to/venv/bin/python parse_markdown.py && /path/to/venv/bin/python insert_into_db.py
```

## Data Safety

Database updates are incremental. Existing investor rows are matched by firm
name. When a new scrape returns sparse data, existing non-empty investor fields
are preserved. Partner and portfolio child records are replaced only when new
non-empty partner or portfolio data is available.

Before switching from test mode to production mode, run against a database
backup or staging database first.

## Tests

Run lightweight tests:

```bash
pytest
```

The current tests focus on safe normalization of legacy and structured partner
and portfolio records.

## Moving Data Into A Shared Database

Use JSON export/import when merging local databases into a shared Supabase or
hosted Postgres database. Do not copy raw table rows by `id`, because different
local databases can reuse the same ids for different investors.

Export from a local database:

```bash
python export_investors_json.py exports/my_investors.json
```

Then point `.env` to the shared database and import:

```bash
python import_investors_json.py exports/my_investors.json
```

The import uses the existing investor upsert logic in `insert_into_db.py`.
Investor records are matched by case-insensitive firm name. Existing rows are
updated, and new firms are inserted. Partners and portfolio companies are
deduplicated within each imported record.

Recommended collaboration flow:

```text
Person A local DB -> export JSON
Person B local DB -> export JSON
Shared Supabase DB -> import both JSON files
```

If the same firm uses different names, for example `BVP` and `Bessemer Venture
Partners`, review those manually after import.
