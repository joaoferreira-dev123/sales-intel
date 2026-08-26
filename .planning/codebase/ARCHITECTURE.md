<!-- refreshed: 2026-08-26 -->
# Architecture

**Analysis Date:** 2026-08-26

## System Overview

```text
┌──────────────────────────────────────────────────────────────┐
│                    Web UI / Browser                           │
│                  `static/index.html`                          │
└────────────────────────┬─────────────────────────────────────┘
                         │ POST /api/briefings
                         ▼
┌──────────────────────────────────────────────────────────────┐
│              FastAPI Application                              │
│              `app/main.py`                                    │
│  - Route handlers                                             │
│  - Request validation (BriefingRequest schema)                │
│  - Response formatting (BriefingResponse schema)              │
└────────────┬─────────────────────────────┬───────────────────┘
             │                             │
             │ lookup/save                 │ use pluggable
             ▼                             ▼
    ┌─────────────────┐          ┌──────────────────┐
    │  Cache Layer    │          │ Extractor Layer  │
    │  `app/db.py`    │          │ `app/extractor.py`
    │                 │          │                  │
    │ SQLite backing  │          │ ┌──────────────┐ │
    │                 │          │ │ Heuristic    │ │
    │ (briefings.db)  │          │ │ (No API key) │ │
    │                 │          │ └──────────────┘ │
    │                 │          │ ┌──────────────┐ │
    │                 │          │ │ LLM          │ │
    │                 │          │ │ (API based)  │ │
    │                 │          │ └──────────────┘ │
    └─────────────────┘          └────────┬─────────┘
                                          │ asks for text
                                          ▼
                                 ┌──────────────────────┐
                                 │ Fetcher/Extractor    │
                                 │ `app/fetcher.py`     │
                                 │                      │
                                 │ - robots.txt check   │
                                 │ - HTTP fetch         │
                                 │ - Text extraction    │
                                 │ - Validation         │
                                 └──────────────────────┘
                                          │
                                          ▼
                                    External Websites
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI App | HTTP request routing, validation, response formatting | `app/main.py` |
| Cache Layer | SQLite persistence, TTL-based invalidation (7 days) | `app/db.py` |
| Extractor (abstraction) | Plugin interface for text-to-briefing transformation | `app/extractor.py` |
| Heuristic Extractor | Regex-based extraction (no API costs, always available) | `app/extractor.py` |
| LLM Extractor | AI-powered extraction (future, requires API key) | `app/extractor.py` |
| Fetcher | HTTP client, robots.txt compliance, text cleaning | `app/fetcher.py` |
| Data Models | Request/response validation schemas | `app/schemas.py` |
| Frontend | Single-page web UI for sales reps | `static/index.html` |

## Pattern Overview

**Overall:** Layered architecture with pluggable extractors and cache-first design.

**Key Characteristics:**
- **Protocol-based abstraction**: Extractors implement a common `Extractor` Protocol; caller doesn't know which implementation is running
- **Graceful degradation**: Heuristic extractor acts as fallback when LLM API unavailable
- **Cache-first strategy**: All URLs checked in cache before network request; 7-day TTL
- **Fault isolation**: Single URL failure doesn't interrupt entire batch; user gets partial results with confidence indicators
- **Pure functions where possible**: HTML text extraction is testable without network

## Layers

**Request Handling (HTTP):**
- Purpose: Accept URLs, validate input, return structured briefings
- Location: `app/main.py`
- Contains: FastAPI routes, request/response handling, orchestration logic
- Depends on: Schemas, Cache, Extractor, Fetcher
- Used by: Browser clients (UI)

**Briefing Extraction (Business Logic):**
- Purpose: Transform raw text into structured briefing with confidence scoring
- Location: `app/extractor.py`
- Contains: Two implementations (Heuristic, LLM) sharing `Extractor` protocol
- Depends on: Schemas (for Briefing output model)
- Used by: Request handler in main.py

**Data Access (Persistence):**
- Purpose: Cache briefings by URL, manage TTL, provide history
- Location: `app/db.py`
- Contains: SQLite connection management, CRUD operations, date-based invalidation
- Depends on: Built-in sqlite3, datetime
- Used by: Request handler for cache lookups and saves

**Web Fetching (Network I/O):**
- Purpose: Safely fetch HTML from external websites, extract readable text
- Location: `app/fetcher.py`
- Contains: robots.txt compliance, HTTP client, HTML → text conversion, error handling
- Depends on: httpx (HTTP client), BeautifulSoup (HTML parsing), lxml (parser backend)
- Used by: Request handler when cache miss occurs

**Data Models (Validation):**
- Purpose: Define request/response schemas with Pydantic validation
- Location: `app/schemas.py`
- Contains: `Briefing` (core output), `BriefingRequest`, `BriefingResponse`
- Depends on: Pydantic, datetime, typing
- Used by: main.py, extractor.py, db.py

**Frontend (UI):**
- Purpose: Browser interface for sales reps to input URLs and view briefings
- Location: `static/index.html`
- Contains: HTML form, JavaScript fetch logic, response rendering
- Depends on: None (vanilla JavaScript, no frameworks)
- Used by: End users

## Data Flow

### Primary Request Path: New URL (Cache Miss)

1. **Request arrives** (`app/main.py:gerar_briefings`) - Sales rep submits 1-10 URLs
2. **Input validated** - Pydantic validates `BriefingRequest` format (URLs are `HttpUrl` type)
3. **Cache lookup** - For each URL, `db.buscar(url)` checks if valid cached entry exists
4. **Cache miss** - No valid entry found (or `forcar_atualizacao=True`)
5. **robots.txt check** - `fetcher.pode_raspar(url)` verifies ethical scraping permission
6. **HTML fetch** - `fetcher.buscar_html(url)` downloads page with timeout (15s) and size limit (3MB)
7. **Text extraction** - `fetcher.extrair_texto(html)` converts HTML to readable text (pure function)
8. **Extractor selected** - `extractor.escolher_extrator()` picks LLM (if API key present) or Heuristic fallback
9. **Briefing generated** - `extrator.extrair(url, titulo, texto)` produces structured `Briefing` object
10. **Persisted** - `db.salvar(url, briefing_dict, extrator_name)` stores in SQLite with UTC timestamp
11. **Response built** - `BriefingResponse` wraps briefing with metadata (origin="novo", extrator name, timestamp)
12. **Response returned** - All briefings sent as JSON array to client

### Cache Hit Path: Existing Valid URL

1. **Request arrives** and enters loop for each URL
2. **Cache lookup** - `db.buscar(url)` returns cached entry if found AND (now - coletado_em) < 7 days
3. **Validation passes** - Cached `Briefing` data loaded from JSON, extractor name and date retrieved
4. **Response built** - `BriefingResponse` with origin="cache" (no extraction or fetching happens)
5. **Response returned** - Cached briefing sent to client

### Error Path: Fetch/Extraction Failure

1. **URL fails at any step** (robots.txt blocks, HTTP error, timeout, not HTML, LLM unavailable, etc.)
2. **FetchError caught** - `FetchError` exception raised with descriptive message
3. **Fallback briefing created** - Generic `Briefing` with low confidence ("baixa") explaining the error
4. **Recorded as failure** - origem="novo", extrator="falha", but still added to results
5. **Request continues** - Failure doesn't interrupt other URLs; batch completes with partial results

**State Management:**
- **Stateless request handling**: Each request is independent; no session state in API
- **Persistent cache only**: State lives in SQLite, keyed by URL
- **No in-memory state**: No caching between requests; each request queries database fresh
- **UTC timestamps**: All dates stored and compared in UTC timezone

## Key Abstractions

**Extractor Protocol:**
- Purpose: Define interface that both Heuristic and LLM implementations must follow
- Examples: `HeuristicExtractor` (static regex patterns), `LLMExtractor` (API-based with JSON validation)
- Pattern: Python `Protocol` (structural typing) — caller doesn't know concrete type, only that `extrair()` method exists and returns `Briefing`
- Enables: Transparent swapping of implementations without changing caller code

**Briefing Schema:**
- Purpose: Represent the structured output that sales reps actually need (not raw HTML)
- Core fields: `empresa` (name), `resumo` (what they do), `segmento` (industry), `porte_estimado` (size), `produtos`, `publico_alvo`, `sinais_recentes` (conversation hooks), `dores_provaveis` (sales angles), `ganchos_de_conversa` (opening lines), `contatos` (emails/phones), `confianca` (confidence level)
- Pattern: Pydantic `BaseModel` with JSON serialization; all optional fields have sensible defaults to prevent "briefing with missing data" errors

**FetchError Exception:**
- Purpose: Carry detailed error messages through exception handling to show sales rep what went wrong
- Pattern: Custom exception class inheriting from `Exception`, message explains the problem (robots.txt block, 404, timeout, etc.)

## Entry Points

**FastAPI Application:**
- Location: `app/main.py`
- Triggers: When uvicorn starts the server
- Responsibilities: Register routes, initialize database, mount static files, serve UI

**POST /api/briefings:**
- Location: `app/main.py:gerar_briefings(req: BriefingRequest)`
- Triggers: When sales rep submits URLs from UI
- Responsibilities: Orchestrate cache lookup → fetch → extract → persist → respond

**GET /api/historico:**
- Location: `app/main.py:historico(limite: int = 50)`
- Triggers: When admin views history page
- Responsibilities: Return list of all briefings ever generated, sorted by recency

**GET /health:**
- Location: `app/main.py:health()`
- Triggers: External monitoring systems
- Responsibilities: Return 200 OK to indicate server is running

**GET / (root):**
- Location: `app/main.py:home()`
- Triggers: When user navigates to domain root
- Responsibilities: Serve `static/index.html`

## Architectural Constraints

- **Threading:** Single-threaded async event loop (Uvicorn/ASGI); no worker threads or multiprocessing
- **Global state:** Minimal — no module-level singletons except database connection pool (created on demand in `db.conectar()`)
- **Circular imports:** None detected; dependency flow is acyclic: main.py → extractor/fetcher/db/schemas
- **Database concurrency:** SQLite has write-locking limitations; not suitable for multi-process deployments; upgrade to PostgreSQL for scaling
- **Cache invalidation:** Simple TTL-based (7 days); no manual invalidation endpoint. Update requires re-fetching with `forcar_atualizacao=True`
- **Async/await:** Not used; all I/O is synchronous (blocking). httpx client created fresh per request (not ideal for high throughput; could be pooled)
- **API key protection:** LLM API key stored only in environment variable `LLM_API_KEY`; never logged or exposed in error messages

## Error Handling

**Strategy:** Fault isolation with graceful degradation.

**Patterns:**
- **Network errors** (timeout, connection refused) → Catch `httpx.RequestError`, create low-confidence briefing with error explanation
- **HTTP errors** (4xx, 5xx) → Catch `httpx.HTTPStatusError`, extract status code, explain to user
- **robots.txt block** → Check before attempting fetch, raise `FetchError` with permission explanation
- **Invalid content type** → Verify `content-type: text/html` before parsing, raise `FetchError` if mismatch
- **Oversized pages** → Check content length before parsing, reject if >3MB
- **LLM unavailable** → If `LLMExtractor.disponible()` is False, silently fall back to `HeuristicExtractor`
- **Database errors** → Let sqlite3 exceptions bubble up (indicates server misconfiguration); should be caught in production wrapper
- **Validation errors** → Pydantic automatically returns 422 Unprocessable Entity with field-level error details

## Cross-Cutting Concerns

**Logging:** None currently implemented. All errors surfaced to user via low-confidence briefings.

**Validation:** 
- Input: Pydantic validates `BriefingRequest` (URLs must be valid `HttpUrl`, 1-10 count enforced)
- Output: Pydantic validates `Briefing` before storing (LLM-generated JSON must conform or raises error)
- Cache: No validation; trust that stored JSON is correct (risk if manual database edits)

**Authentication:** None in current MVP. Security requirement (Bonus 2) not yet implemented.

**Resilience:**
- No retries: Single attempt per URL; failure is final
- No circuit breaker: Each URL fetched independently; site latency doesn't affect others
- No timeout cascade: Each component has its own timeout (15s for fetch, implicit timeout on text extraction)

---

*Architecture analysis: 2026-08-26*
