# Technology Stack

**Analysis Date:** 2026-08-26

## Languages

**Primary:**
- Python 3.12 - Backend API and business logic

**Frontend:**
- HTML5 - Static markup served from `static/index.html`
- CSS3 - Inline styles in HTML
- Vanilla JavaScript - Client-side form handling and API calls

## Runtime

**Environment:**
- Python 3.12.10

**Package Manager:**
- pip
- Lockfile: `requirements.txt` present (no pinned versions)

## Frameworks

**Core:**
- FastAPI 0.104+ - REST API framework for `/api/briefings`, `/api/historico`, `/health` endpoints
- Uvicorn (with standard extras) - ASGI server for running FastAPI app

**Testing:**
- pytest - Test runner (config from `.pytest_cache` in repo root)

**Validation:**
- Pydantic - Data validation for `BriefingRequest`, `BriefingResponse`, and `Briefing` models in `app/schemas.py`

**Build/Dev:**
- Python built-in modules: `urllib`, `sqlite3`, `json`, `pathlib`, `datetime`

## Key Dependencies

**Critical:**
- FastAPI - Web framework providing REST API structure in `app/main.py`
- Pydantic - Schema validation ensuring structured briefing data from `app/schemas.py`
- httpx - HTTP client for fetching website content in `app/fetcher.py`
- BeautifulSoup4 - HTML parsing and text extraction in `app/fetcher.py:extrair_texto()`
- lxml - XML/HTML parsing backend for BeautifulSoup in `app/fetcher.py`

**Data & Persistence:**
- sqlite3 (built-in) - Local database for briefing cache in `app/db.py`, stored as `briefings.db`

**Infrastructure:**
- Uvicorn - ASGI application server
- urllib (built-in) - robots.txt parsing in `app/fetcher.py:pode_raspar()`

## Configuration

**Environment:**
- Environment variable: `LLM_API_KEY` - For future LLM integration (checked in `app/extractor.py:LLMExtractor`)
- No `.env` file in current repo - Configuration via OS environment only
- Static file serving: `static/` directory mounted at `/static` in `app/main.py`

**Build:**
- No build step required - Pure Python application
- Direct execution: `uvicorn app.main:app` or similar

## Platform Requirements

**Development:**
- Python 3.12+
- pip package manager
- Virtual environment recommended (`.venv/` present in repo)

**Production:**
- Python 3.12+ runtime environment
- Uvicorn ASGI server
- SQLite database file writable location
- Network access to external websites for scraping
- Optional: LLM API key (OpenAI GPT-4o-mini) for enhanced extraction

---

*Stack analysis: 2026-08-26*
