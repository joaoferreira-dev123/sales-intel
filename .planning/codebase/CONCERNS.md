# Codebase Concerns

**Analysis Date:** 2026-08-26

## Tech Debt

**Unimplemented LLM Integration:**
- Issue: `LLMExtractor.extrair()` raises `NotImplementedError` at `app/extractor.py:89`. System crashes with HTTP 500 if `LLM_API_KEY` env var is set, since `main.py:75` only catches `FetchError`, not generic exceptions from extractors.
- Files: `app/extractor.py:83-89`, `app/main.py:47`, `app/main.py:75-83`
- Impact: Demo becomes unstable the moment LLM API key is configured. Entire batch fails if one extractor raises exception.
- Fix approach: Complete LLMExtractor implementation with proper error handling in main.py loop to catch all extractor exceptions and degrade to heuristic.

**Missing Configuration Module:**
- Issue: Environment variables scattered across code (`extractor.py:77` reads `LLM_API_KEY` via `os.getenv()`). No `app/config.py` file as specified in SPEC §4, §12.
- Files: `app/extractor.py:77-78`
- Impact: Configuration management is fragmented; no single source of truth for env vars. Deploying to production requires understanding multiple files.
- Fix approach: Create `app/config.py` centralizing LLM configuration (`LLM_API_KEY`, `LLM_MODELO`, `LLM_MAX_CHARS`) with validation. Create `.env.example` per SPEC §17.

**Character Encoding Mojibake in Frontend:**
- Issue: `static/index.html` contains double-encoded UTF-8 sequences: `reuni\xc3\x83\xc2\xa3o` renders as "reuniÃ£o" in browser. Visible in lines 39, 96, 102 where Portuguese characters are corrupted.
- Files: `static/index.html:39`, `static/index.html:96`, `static/index.html:102`
- Impact: UI renders incorrectly during live demo (visible at 17h presentation). User sees "reuniÃ£o" instead of "reunião", "confianÃ§a" instead of "confiança".
- Fix approach: Remove BOM and fix file encoding to UTF-8 without BOM. Re-encode all non-ASCII content.

**Missing Schema Migration System:**
- Issue: SQLite schema has no migration mechanism. SPEC §8 defines `conteudo_hash` column for change detection, but `db.py:27-37` uses `CREATE TABLE IF NOT EXISTS` which doesn't alter existing tables. With `briefings.db` already present, adding columns requires manual `ALTER TABLE` or deletion.
- Files: `app/db.py:27-37`
- Impact: Schema cannot evolve safely without manual intervention or data loss. Deploying with schema changes to machines with existing databases will silently skip the new columns.
- Fix approach: Implement migration helper checking schema version, running ALTER TABLE statements conditionally, or auto-deleting stale cache before schema changes.

**Hardcoded Database Path:**
- Issue: `DB_PATH = Path("briefings.db")` in `app/db.py:17` uses relative path. Breaks if application is run from different working directory.
- Files: `app/db.py:17`
- Impact: Containerization fails; data ends up in unexpected locations; production deployments may lose data if cwd varies.
- Fix approach: Use absolute path or load from config: `Path(__file__).parent.parent / "briefings.db"` or from `DATABASE_URL` env var.

**Non-Absolute Static File Paths:**
- Issue: `app.mount("/static", StaticFiles(directory="static"), name="static")` and `FileResponse("static/index.html")` in `app/main.py:104, 109` use relative paths. Fails when app is started from directories other than project root.
- Files: `app/main.py:104`, `app/main.py:109`
- Impact: Serving static files breaks in Docker, systemd services, or any deployment where cwd ≠ project root. UI becomes inaccessible.
- Fix approach: Use absolute paths: `Path(__file__).parent.parent / "static"` for both mount and home route.

## Known Bugs

**robots.txt Fetch Hangs Indefinitely:**
- Symptoms: Single slow domain can hang the entire fetch operation during robots.txt read.
- Files: `app/fetcher.py:27-37`
- Trigger: Access a domain with slow/unresponsive robots.txt server. The `urllib.robotparser.RobotFileParser.read()` call has no timeout.
- Workaround: Set system-level timeout for HTTP requests (not ideal). Ctrl+C to interrupt.
- Root cause: `fetcher.py:32-36` uses `parser.read()` without timeout. The wrapper `buscar_html()` has `TIMEOUT = 15.0` for the page fetch, but `pode_raspar()` is called first and has no timeout.
- Fix approach: Wrap `parser.read()` in `httpx` call with explicit 5s timeout, or set socket timeout context.

**Extractor Selection Per-Request, Not Per-URL:**
- Symptoms: If LLM fails midway through processing 10 URLs, the fallback extractor is not automatically used for remaining URLs.
- Files: `app/main.py:47`
- Trigger: LLM becomes unavailable (API down, quota exceeded) after processing first URL successfully.
- Current state: `escolher_extrator()` is called once before the loop. If implementation changes to check availability per URL, it works; currently it does not.
- Fix approach: Call `escolher_extrator()` inside the loop for each URL, or add try/except around extractor call to degrade gracefully per URL.

## Security Considerations

**Hardcoded User-Agent with Personal Email:**
- Risk: User-Agent string `"bna-sales-intel/0.1 (+contato: gabriel@bna.dev.br)"` exposes personal email address in all HTTP requests. Can be harvested by upstream proxies, logs, and security tools.
- Files: `app/fetcher.py:17`
- Current mitigation: Email belongs to Gabriel at bna.dev, but is still personally identifiable in logs.
- Recommendations: Use generic email or no contact info: `"bna-sales-intel/0.1 (contact: support@bna.dev)"`, or move to environment variable for production deployments.

**Missing Input Validation on URL Length:**
- Risk: `BriefingRequest.urls` accepts `list[HttpUrl]` with `min_length=1, max_length=10` but individual URL length is unbounded. Malformed URLs or URLs with extremely long query strings could cause memory issues.
- Files: `app/schemas.py:65`
- Current mitigation: Pydantic validates URL format but not length.
- Recommendations: Add `max_length` constraint to `HttpUrl` or validate total payload size.

**No Request Size Limit:**
- Risk: No limit on total JSON payload size. Sending 10 URLs with very long query parameters could consume server memory.
- Files: `app/main.py:39`
- Current mitigation: None.
- Recommendations: Add FastAPI middleware or Pydantic validator to reject payloads > ~100KB.

**Prompt Injection Risk (Partially Mitigated):**
- Risk: SPEC §11 warns that page content can contain hidden instructions trying to redirect the LLM. While `LLMExtractor` is not yet implemented, the prompt strategy must separate instruction from content clearly.
- Files: `app/extractor.py:64-89` (future LLMExtractor.extrair implementation)
- Current mitigation: Not implemented yet. Spec §11 and §16 define mitigation: separate system message from page content, validate output with schema.
- Recommendations: When implementing LLMExtractor, use system message + separate data message with delimiters. See SPEC §11 for exact mitigations.

## Performance Bottlenecks

**robots.txt Fetched on Every Request:**
- Problem: `pode_raspar()` in `fetcher.py:27` is called for every URL in every request. No caching of robots.txt results. Domain policies rarely change within minutes.
- Files: `app/fetcher.py:27-37`, called from `app/main.py:69` inside the loop
- Cause: Each URL triggers a fresh robots.txt parse. With 10 URLs, 10 HTTP requests to robots.txt even if they're from the same domain.
- Improvement path: Implement per-domain robots.txt cache (TTL 1 hour) using dictionary or Redis later. Reduces 90% of early-phase requests.

**Regex for Email/Phone Too Simplistic:**
- Problem: `EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")` and `TEL_RE = re.compile(r"\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}")` are basic patterns. Many valid contact formats go undetected.
- Files: `app/extractor.py:27-28`
- Cause: Heuristic extractor uses hand-written regex instead of proven libraries.
- Improvement path: Use `email-validator` library for emails. For phones, add support for international formats (+55 prefix, 11 99999-9999 pattern, extensions).

**Text Extraction Splits All Lines:**
- Problem: `extrair_texto()` in `fetcher.py:86-90` splits on all `\n` then filters lines < 3 chars. This rebuilds the entire text even for unchanged domains, re-parsing with BeautifulSoup every time.
- Files: `app/fetcher.py:68-90`
- Cause: Extraction is not cached. Same page fetched twice parses HTML twice.
- Improvement path: Cache extracted text (with content hash per SPEC §8) so re-fetches skip extraction.

## Fragile Areas

**HeuristicExtractor Company Name Extraction:**
- Files: `app/extractor.py:48-50`
- Why fragile: Assumes company name is first part of `<title>` before `|` or `-`. Title format varies wildly: "About Us | Company Name" vs "Company Name - Solutions" vs "Company Name". Current split will fail or return partial names.
- Safe modification: Add fallback to URL domain name if title parsing fails (already done: `or url`). Test against 10+ real title formats.
- Test coverage: `test_smoke.py:23-24` covers happy path, but no tests for variations like "Acme - The Platform for X | Solutions".

**HTML Parsing Dependency on BeautifulSoup + lxml:**
- Files: `app/fetcher.py:74`
- Why fragile: Hard-coded `"lxml"` parser. If lxml is not installed (missing from some minimal environments), silently falls back to html.parser which may produce different results. No fallback strategy.
- Safe modification: Check if lxml available, else log warning and use html.parser explicitly.
- Test coverage: No tests for parser availability or missing lxml scenario.

**Database Concurrent Access:**
- Files: `app/db.py:21-24`, all functions use `conectar()` creating new connection per call
- Why fragile: SQLite allows only one writer at a time. If two requests try to write simultaneously, the second gets LOCKED error. FastAPI runs multiple workers in production.
- Safe modification: Add connection pooling or WAL mode (`PRAGMA journal_mode=WAL`) to handle concurrent writes.
- Test coverage: No concurrency tests.

**Cache Validity Check Uses Local Timezone:**
- Files: `app/db.py:52-54`
- Why fragile: `datetime.now(timezone.utc)` compared against stored `datetime.fromisoformat()`. If stored timestamp lacks timezone info, comparison is naive vs aware, raising TypeError.
- Safe modification: Always store timestamps with explicit timezone (current code does via `agora.isoformat()` in `salvar()`). Add assertion in `buscar()` that coletado_em is aware.
- Test coverage: No tests for mixed naive/aware timestamps.

## Scaling Limits

**SQLite Scalability:**
- Current capacity: Tested with ~3 entries in `briefings.db`. SPEC uses it for prototype only.
- Limit: SQLite bottlenecks around 1M rows (depending on query patterns). With daily use and 100 URLs/day, reaches limit in ~27 years, but concurrent writes will fail much sooner.
- Scaling path: Migrate to PostgreSQL (SPEC §7 notes it's the intent). Swap `db.py` to use `psycopg2` or `sqlalchemy` without touching callers.

**Robots.txt Cache Unbounded:**
- Current capacity: Stores one robots.txt parse result per domain. No eviction.
- Limit: If bot crawls 10k unique domains, one entry per domain, memory grows without bound.
- Scaling path: Implement LRU cache with max size (e.g., 1000 domains) or TTL (1 hour).

**LLM Token Cost Unbounded (When Implemented):**
- Current capacity: Text cut at 12k chars, single request per URL.
- Limit: With 10 URLs × 12k chars = 120k tokens per request, at OpenAI rates (~$0.0003/1k tokens), each call costs ~$0.04. 100 requests/day = $4/day.
- Scaling path: Implement token counting before API call, reject oversized batches, add quota enforcement per user (requires auth from Fase 6).

## Dependencies at Risk

**Deprecated FastAPI Pattern:**
- Risk: `@app.on_event("startup")` in `app/main.py:28-30` is deprecated since FastAPI 0.93. Future versions will remove it.
- Files: `app/main.py:28-30`
- Impact: Code breaks on upgrade to FastAPI 0.100+.
- Migration plan: Replace with `@app.lifespan` context manager (backwards compatible since FastAPI 0.92). Current workaround: pin FastAPI version in requirements.txt.

**BeautifulSoup4 Without Explicit Parser:**
- Risk: `BeautifulSoup(html, "lxml")` requires lxml to be installed separately. If removed from requirements, parsing fails silently or falls back to less robust parser.
- Files: `app/fetcher.py:74`
- Impact: HTML extraction produces unexpected results; extractor gets garbage input.
- Migration plan: Explicit test for lxml availability, or switch to `html.parser` (built-in to Python, but slower and less robust).

**Pydantic v2 Response Validation:**
- Risk: Code uses Pydantic `BaseModel` which is compatible with both v1 and v2, but `response_model` in `app/main.py:38` assumes v2 behavior. Upgrading to Pydantic 2.x changes validation errors.
- Files: `app/main.py:38`
- Impact: API response format may change on Pydantic upgrade; API contracts may break.
- Migration plan: Pin Pydantic version in requirements.txt, or test response serialization explicitly.

## Missing Critical Features

**Feature Gap: Content Change Detection:**
- Problem: SPEC §8 defines `conteudo_hash` column to detect when page content changes (invalidating cache). Not implemented.
- Blocks: Can't reliably refresh cache when client updates their website. Cache becomes stale.
- Implementation: Hash the extracted text at `fetcher.py:86` with `hashlib.sha256()`, store in DB, compare on next fetch.

**Feature Gap: Extractor Selection Per-URL:**
- Problem: `escolher_extrator()` runs once per request. If LLM fails midway, other URLs don't fall back.
- Blocks: Resilience during demo if LLM becomes unavailable mid-batch.
- Implementation: Move extractor selection inside the loop in `main.py:50-93`.

**Feature Gap: User Authentication & Authorization (Fase 6):**
- Problem: No login, no API key auth, no rate limiting. `/api/historico` endpoint is public.
- Blocks: Multi-user deployments, billing, audit trails.
- Implementation: SPEC §15 Phase 6 includes auth. Out of scope for Phase 5.

## Test Coverage Gaps

**Untested: Extractor Exception Handling:**
- What's not tested: If an extractor raises an exception other than `FetchError`, is it caught and degraded?
- Files: `app/main.py:75-83` only catches `FetchError`, not generic `Exception`
- Risk: LLMExtractor NotImplementedError will crash the entire batch. Task will be marked as failed when the intent is to return partial results.
- Priority: **High** — this is a live demo blocker. Fix before Phase 5 ends.

**Untested: robots.txt Failure & Timeouts:**
- What's not tested: Behavior when robots.txt is unreachable (domain down, 404, timeout).
- Files: `app/fetcher.py:34-36` catches generic `Exception` and returns `True`, but never raises timeout.
- Risk: Slow robots.txt server hangs the entire request for 30+ seconds (OS timeout, not code timeout).
- Priority: **High** — demo stability risk.

**Untested: Email/Phone Extraction Coverage:**
- What's not tested: Regex coverage of real-world formats (extensions, +55 prefix, hyphens, international).
- Files: `app/extractor.py:27-28`
- Risk: Valid contacts are missed, briefing looks incomplete.
- Priority: **Medium** — affects quality, not stability.

**Untested: Concurrent Requests to Same URL:**
- What's not tested: Does SQLite handle `INSERT OR UPDATE` if two requests write simultaneously?
- Files: `app/db.py:62-70`
- Risk: SQLITE_BUSY error, request hangs or crashes.
- Priority: **Medium** — low probability in small deployments, high impact in production.

**Untested: Cache Expiry Edge Cases:**
- What's not tested: Behavior at exactly 7 days (off-by-one), timezone-aware vs naive timestamps, DST transitions.
- Files: `app/db.py:52-54`
- Risk: Cache returned after 7 days, or not returned after 6 days.
- Priority: **Low** — unlikely to cause visible bugs, but indicates incomplete test coverage.

**Untested: HTML with No Title Tag:**
- What's not tested: `extrair_texto()` when `<title>` is missing.
- Files: `app/fetcher.py:84`
- Risk: `if soup.title` handles it, but test coverage is missing.
- Priority: **Low** — code is defensive, but pattern needs test.

**Untested: Very Large Pages:**
- What's not tested: Behavior when page is exactly 3MB (the `MAX_BYTES` limit).
- Files: `app/fetcher.py:62-63`
- Risk: Boundary condition, off-by-one error.
- Priority: **Low** — rare, but important for robustness.

---

*Concerns audit: 2026-08-26*
