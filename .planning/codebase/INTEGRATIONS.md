# External Integrations

**Analysis Date:** 2026-08-26

## APIs & External Services

**Web Scraping:**
- Arbitrary client websites - Dynamic discovery via user input
  - SDK/Client: httpx (HTTP client in `app/fetcher.py`)
  - No authentication needed for public websites
  - robots.txt compliance checked before each request in `app/fetcher.py:pode_raspar()`
  - User-agent: `bna-sales-intel/0.1 (+contato: gabriel@bna.dev.br)`
  - Timeout: 15 seconds (constant `TIMEOUT` in `app/fetcher.py`)
  - Max payload: 3MB (constant `MAX_BYTES` in `app/fetcher.py`)

**LLM (Planned, Not Yet Active):**
- OpenAI API - Future integration for structured briefing generation
  - Model: gpt-4o-mini (default in `app/extractor.py:LLMExtractor`)
  - Auth: Environment variable `LLM_API_KEY`
  - Status: Not implemented (see `app/extractor.py:LLMExtractor.extrair()` raises `NotImplementedError`)
  - Text limit: 12,000 characters per request (cost optimization)
  - Fallback: HeuristicExtractor runs when API key unavailable in `app/extractor.py:escolher_extrator()`

## Data Storage

**Databases:**
- SQLite 3 (embedded)
  - File: `briefings.db` (local, relative to working directory)
  - Connection: Direct file connection via sqlite3 module in `app/db.py:conectar()`
  - Tables: Single `briefings` table with URL primary key, briefing JSON, extractor name, timestamp
  - Cache validity: 7 days (constant `VALIDADE` in `app/db.py`)
  - No ORM - Raw SQL with Pydantic model validation

**File Storage:**
- Local filesystem only
  - Static assets: `static/` directory containing `static/index.html`
  - Database file: `briefings.db` in project root

**Caching:**
- Built-in SQLite cache layer in `app/db.py`
- Cache bypass: Optional `forcar_atualizacao: bool` flag in `BriefingRequest` schema
- Cache hits returned from `app/db.py:buscar()` → skips `buscar_html()` call

## Authentication & Identity

**Auth Provider:**
- None - Public API with no user authentication
- Future: Bonus 2 mentions optional auth and admin area (not yet implemented)
- robots.txt consultation serves as ethical "authentication" to respect site access policies

## Monitoring & Observability

**Error Tracking:**
- None configured
- Custom `FetchError` exception in `app/fetcher.py` provides structured failure messages to clients
- Errors converted to low-confidence briefings in `app/main.py:gerar_briefings()` (lines 75-83)

**Logs:**
- No structured logging configured
- Debug-friendly approach: User-agent includes contact email for site administrators to report issues

## CI/CD & Deployment

**Hosting:**
- Not specified - Runs locally on uvicorn
- Production deployment: Docker Compose mentioned in SPEC-sales-intel.md but not implemented yet
- Expected: Customer server deployment per `SPEC-sales-intel.md` section 1

**CI Pipeline:**
- None detected
- Test suite: pytest with smoke tests in `test_smoke.py`
- Run tests: `pytest test_smoke.py`

## Environment Configuration

**Required env vars:**
- `LLM_API_KEY` - Optional, enables LLM extractor; if absent, falls back to heuristic extractor (checked in `app/extractor.py:LLMExtractor.disponivel()`)

**Optional env vars:**
- None beyond LLM_API_KEY

**Secrets location:**
- Environment variables only
- No `.env` file in repository (ignored by `.gitignore`)
- Safe for customer deployment: no secrets in code

## Webhooks & Callbacks

**Incoming:**
- None - HTTP polling only (clients POST to `/api/briefings`)

**Outgoing:**
- None - No callbacks to external services
- Future: Possible webhook/export for CRM integration (listed as "Fica de fora" in SPEC-sales-intel.md section 4)

## Data Flow

**Request → Response:**
1. Client POST to `/api/briefings` with URL list (`BriefingRequest` in `app/schemas.py`)
2. For each URL in parallel loop (`app/main.py:gerar_briefings()`):
   - Check SQLite cache via `app/db.py:buscar()` (7-day validity)
   - If cache hit: return cached `Briefing` + metadata
   - If cache miss or forced update:
     - `app/fetcher.py:pode_raspar()` → check robots.txt
     - `app/fetcher.py:buscar_html()` → httpx GET with 15s timeout
     - `app/fetcher.py:extrair_texto()` → BeautifulSoup HTML → (title, text)
     - Choose extractor: `app/extractor.py:escolher_extrator()` (LLM if key exists, else heuristic)
     - `app/extractor.py.HeuristicExtractor.extrair()` or `LLMExtractor.extrair()` → `Briefing` object
     - Save via `app/db.py:salvar()` to SQLite
   - Catch `FetchError` → return low-confidence briefing with error message
3. Return list of `BriefingResponse` with origin ("cache" or "novo"), extractor name, timestamp

---

*Integration audit: 2026-08-26*
