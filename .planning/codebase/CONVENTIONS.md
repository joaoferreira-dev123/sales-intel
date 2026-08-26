# Coding Conventions

**Analysis Date:** 2026-08-26

## Naming Patterns

**Files:**
- Lowercase with underscores for modules: `db.py`, `fetcher.py`, `extractor.py`, `schemas.py`
- Test files: `test_<module>.py` (e.g., `test_smoke.py`)
- Package root: `__init__.py`

**Functions:**
- snake_case for all function names
- Examples: `extrair_texto()`, `buscar_html()`, `pode_raspar()`, `conectar()`, `criar_tabelas()`
- Private functions use no prefix (Python convention doesn't enforce private)

**Classes:**
- PascalCase for all classes
- Examples: `HeuristicExtractor`, `LLMExtractor`, `Briefing`, `BriefingRequest`, `BriefingResponse`, `FetchError`

**Variables:**
- snake_case for all variables and parameters
- Examples: `titulo`, `texto`, `contatos`, `confianca`, `coletado_em`
- Tuple unpacking follows snake_case: `dados, nome_extrator, coletado_em = cache`

**Constants:**
- UPPER_SNAKE_CASE for module-level constants
- Examples: `USER_AGENT`, `TIMEOUT`, `MAX_BYTES`, `VALIDADE`, `EMAIL_RE`, `TEL_RE`, `DB_PATH`

**Type Variables and Protocols:**
- Protocol classes use PascalCase: `Extractor` (line 31 in `app/extractor.py`)

## Code Style

**Formatting:**
- No explicit formatter configured (not ruff, black, or similar in requirements)
- Manual style adherence: 4-space indentation, line breaks for readability
- Lines kept reasonably short (most under 100 chars, visible in `app/main.py`)
- No trailing whitespace

**Linting:**
- No linting tool configured (no .flake8, ruff.toml, or pyproject.toml)
- Style is maintained manually through code review conventions

**Type Hints:**
- Modern Python 3.10+ syntax used throughout: `str | None` instead of `Optional[str]`
- Example: `tuple[dict, str, datetime] | None` (line 41 in `app/db.py`)
- Generic types use lowercase: `list[dict]`, `list[BriefingResponse]`
- Return types always specified: `-> None`, `-> dict`, `-> str`
- Function parameters typed: `def buscar(url: str) -> tuple[dict, str, datetime] | None:`

## Import Organization

**Order:**
1. Standard library (datetime, json, sqlite3, urllib, os, re, pathlib)
2. Third-party packages (fastapi, httpx, pydantic, bs4)
3. Local imports (`.` relative imports within `app` package)

**Example from `app/main.py`:**
```python
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .extractor import escolher_extrator
from .fetcher import FetchError, buscar_html, extrair_texto
from .schemas import Briefing, BriefingRequest, BriefingResponse
```

**Path Aliases:**
- Relative imports use leading dot: `from . import db`, `from .fetcher import ...`
- No path aliases (baseURL or similar) configured

## Error Handling

**Patterns:**
- Custom exception classes inherit from `Exception`: `class FetchError(Exception):`
- Exceptions carry descriptive messages about the error condition
- Raised with context string and original exception chained: `raise FetchError(f"...") from e`
- Specific exception catching: `except FetchError as e:` and `except httpx.HTTPStatusError as e:`
- Broad exception catching only when necessary: `except Exception:` (line 35 in `app/fetcher.py` for robots.txt parsing)
- Error messages are user-facing where appropriate (e.g., FetchError messages shown to salespeople)

**Example from `app/main.py` (lines 75-83):**
```python
except FetchError as e:
    briefing = Briefing(
        empresa=url,
        resumo=f"Nao foi possivel coletar esta pagina. {e}",
        confianca="baixa",
    )
    coletado_em = datetime.now(timezone.utc)
    origem = "novo"
    nome_extrator = "falha"
```

## Logging

**Framework:** `console` (print statements, no logging module imported)

**Patterns:**
- No structured logging configured
- No print statements observed in production code
- Logging handled by FastAPI/uvicorn at server level
- Errors are surfaced via HTTP responses and Briefing objects with low confidence

## Comments

**When to Comment:**
- Module docstrings explain PURPOSE and architectural decisions
- Function docstrings explain WHAT the function does and important context
- Inline comments explain WHY (not what the code does)
- Portuguese language used throughout (matches codebase language and team)

**Example from `app/fetcher.py` (lines 15-16):**
```python
# User-agent identificavel. Raspar escondido e o tipo de coisa que da
# problema legal quando o sistema roda no servidor do cliente.
```

**Docstring Pattern:**
- Module docstring at line 1-8 in most files
- Function docstring immediately after `def` line, explains behavior and edge cases
- No parameter documentation format (no `:param:` style)
- Return value documented in description when non-obvious

**Example from `app/db.py` (lines 41-42):**
```python
def buscar(url: str) -> tuple[dict, str, datetime] | None:
    """Devolve (briefing, extrator, data) se houver cache valido."""
```

## Function Design

**Size:**
- Functions are short and focused (most < 30 lines)
- Example: `pode_raspar()` = 11 lines, `extrair_texto()` = 23 lines
- Longer functions have clear sections separated by blank lines

**Parameters:**
- Functions accept specific named parameters, no *args/**kwargs patterns observed
- Type hints on all parameters
- Default values used for optional params: `def listar(limite: int = 50)` (line 76 in `app/db.py`)

**Return Values:**
- Functions return single values or tuples of values
- Return types always specified
- Example: `def buscar(url: str) -> tuple[dict, str, datetime] | None:`
- Multiple return values returned as tuple: `return titulo, "\n".join(linhas)` (line 90 in `app/fetcher.py`)

**Purity:**
- Text extraction functions are pure (no side effects): `extrair_texto()` in `app/fetcher.py`
- Database functions modify state: `salvar()`, `conectar()`
- Network functions have side effects: `buscar_html()`, `pode_raspar()`
- This separation is intentional for testability

## Module Design

**Exports:**
- Modules export functions and classes intended for use elsewhere
- No `__all__` variable defined anywhere
- Importing uses explicit imports: `from .schemas import Briefing, BriefingRequest, BriefingResponse`

**Responsibility:**
- `app/schemas.py`: Pydantic models and data validation
- `app/db.py`: SQLite operations and caching logic
- `app/fetcher.py`: HTTP fetching and HTML parsing
- `app/extractor.py`: Data extraction logic and strategy pattern
- `app/main.py`: FastAPI routes and request handling

**Barrel Files:**
- Not used - each module imported explicitly by name

## Design Patterns Used

**Protocol/Interface (Strategy):**
- `Extractor` protocol in `app/extractor.py` (line 31-36) defines contract for extractors
- Two implementations: `HeuristicExtractor` and `LLMExtractor`
- Used via `escolher_extrator()` factory function

**Factory Pattern:**
- `escolher_extrator()` (line 92-100 in `app/extractor.py`) returns appropriate extractor
- Degradation: uses LLM if available, falls back to heuristic

**Data Transfer Objects:**
- Pydantic models serve as DTOs: `Briefing`, `BriefingRequest`, `BriefingResponse`
- Validation built into Pydantic: `urls: list[HttpUrl]` validates URL format

## Context Manager Usage

- SQLite connections use context managers: `with conectar() as conn:` (line 43 in `app/db.py`)
- httpx.Client used as context manager: `with httpx.Client(...) as client:` (line 46 in `app/fetcher.py`)
- Ensures cleanup without try/finally boilerplate

---

*Convention analysis: 2026-08-26*
