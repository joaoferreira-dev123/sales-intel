# Testing Patterns

**Analysis Date:** 2026-08-26

## Test Framework

**Runner:**
- pytest (specified in `requirements.txt`)
- Version: Not pinned in `requirements.txt` (any recent version)
- Config: No explicit pytest.ini or pyproject.toml - uses pytest defaults
- Cache directory: `.pytest_cache/` created at project root

**Assertion Library:**
- Python's built-in `assert` statements
- No external assertion library (no pytest-assertions, hamcrest, etc.)

**Run Commands:**
```bash
pytest                    # Run all tests
pytest -v                 # Verbose output with test names
pytest test_smoke.py      # Run single test file
pytest -k <pattern>       # Run tests matching pattern
pytest --collect-only     # List all tests without running
```

## Test File Organization

**Location:**
- Tests co-located at project root: `test_smoke.py`
- No separate `tests/` directory
- Pattern: `test_<name>.py` at project root level

**Naming:**
- Test functions: `test_<behavior_being_tested>()`
- Examples: `test_extrair_texto_remove_script_e_pega_titulo()`, `test_heuristico_monta_briefing()`, `test_heuristico_encontra_contatos()`
- Descriptive names that read like documentation

**Structure:**
```
test_smoke.py
├── Module docstring
├── Test data (fixtures)
└── Test functions
```

## Test Structure

**Suite Organization from `test_smoke.py`:**

```python
"""Testes que rodam sem internet."""
from app.extractor import HeuristicExtractor
from app.fetcher import extrair_texto

HTML = """..."""

def test_extrair_texto_remove_script_e_pega_titulo():
    titulo, texto = extrair_texto(HTML)
    assert titulo == "Acme Tecnologia | Solucoes"
    assert "x=1" not in texto
    assert "automacao industrial" in texto

def test_heuristico_monta_briefing():
    titulo, texto = extrair_texto(HTML)
    b = HeuristicExtractor().extrair("https://acme.com.br", titulo, texto)
    assert b.empresa == "Acme Tecnologia"
    assert "automacao" in b.resumo
    assert b.confianca == "baixa"
```

**Patterns:**
- **Arrange:** No explicit setup methods - test data defined as module-level constant `HTML` (lines 5-13 in `test_smoke.py`)
- **Act:** Call function(s) in test body
- **Assert:** Multiple assertions per test to verify behavior
- **Teardown:** No teardown needed - tests are pure, no side effects

## Mocking

**Framework:** None configured
- No `unittest.mock` imports observed
- No pytest-mock or other mocking library in `requirements.txt`

**Patterns:**
- No mocking observed in `test_smoke.py`
- Tests use real implementations: `HeuristicExtractor().extrair()`
- Tests use real `BeautifulSoup` HTML parsing via `extrair_texto()`

**What to Mock:**
- Network calls (if needed): `httpx.Client` in `app/fetcher.py`
- Database (if testing integration): SQLite in `app/db.py`
- LLM API calls (if testing `LLMExtractor`)

**What NOT to Mock:**
- Pure functions like `extrair_texto()` - test with real data
- Pydantic model validation - test with real models
- Regex patterns for email/phone extraction - test with real regexes

## Fixtures and Factories

**Test Data:**
Module-level fixture in `test_smoke.py` (lines 5-13):
```python
HTML = """
<html><head><title>Acme Tecnologia | Solucoes</title></head>
<body><nav>menu</nav><script>x=1</script>
<p>A Acme Tecnologia desenvolve plataformas de automacao industrial para
industrias de medio porte, com foco em reducao de custo operacional.</p>
<p>Fundada em 2015, atende mais de 200 clientes em todo o Brasil e mantem
operacao propria de suporte tecnico especializado.</p>
<footer>contato@acme.com.br (11) 98888-7777</footer></body></html>
"""
```

**Location:**
- Fixtures defined at module level (module scope)
- Shared across all test functions in `test_smoke.py`
- No pytest fixtures with `@pytest.fixture` decorator

**Pattern:**
- Simple constant data: `HTML` string used as-is
- No factory functions or builders
- Data represents realistic scenario (valid HTML with scripts, navigation, footer)

## Coverage

**Requirements:** Not enforced
- No `coverage` tool in `requirements.txt`
- No coverage thresholds in pytest configuration
- No .coveragerc file

**View Coverage:**
```bash
pip install coverage
coverage run -m pytest
coverage report
coverage html          # Generates htmlcov/index.html
```

## Test Types

**Unit Tests:**
- Scope: Individual functions and classes
- Approach: Test pure functions with fixed input/output
- Examples in `test_smoke.py`:
  - `test_extrair_texto_remove_script_e_pega_titulo()` tests text extraction in isolation
  - `test_heuristico_monta_briefing()` tests `HeuristicExtractor.extrair()` with fixed data

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Not formally separated from unit tests
- Examples in `test_smoke.py`:
  - `test_heuristico_monta_briefing()` integrates text extraction → briefing generation
  - Contact extraction tested as part of briefing generation

**E2E Tests:**
- Framework: Not used
- Note: No end-to-end tests for HTTP endpoints observed
- Future: Would use `TestClient` from fastapi.testclient for `/api/briefings` endpoint

**Smoke Tests:**
- File name `test_smoke.py` indicates "smoke tests" - tests that verify basic functionality
- Comment: "Testes que rodam sem internet" - emphasizes these run offline without external deps

## Common Patterns

**Assertion Patterns:**
```python
# Exact equality
assert titulo == "Acme Tecnologia | Solucoes"

# Membership (substring search)
assert "x=1" not in texto
assert "automacao industrial" in texto

# Object property assertions
assert b.empresa == "Acme Tecnologia"
assert b.confianca == "baixa"

# List membership
assert "contato@acme.com.br" in b.contatos
```

**Testing Pure Functions:**
```python
# Extract text from HTML fixture
titulo, texto = extrair_texto(HTML)

# Verify both outputs
assert titulo == "..."
assert "..." in texto
```

**Testing Class Methods:**
```python
# Instantiate extractor
b = HeuristicExtractor().extrair("https://acme.com.br", titulo, texto)

# Verify returned object properties
assert b.empresa == "Acme Tecnologia"
assert b.confianca == "baixa"
```

## Test Characteristics

**Independence:**
- Each test is independent - no test ordering required
- Tests don't share state (except module-level HTML fixture for reading)
- No setup/teardown dependencies

**Repeatability:**
- Tests are deterministic - same input always produces same output
- No random data or time-dependent assertions
- Can run tests multiple times with same results

**Clarity:**
- Test names are descriptive and self-documenting
- Test body is easy to follow: Arrange → Act → Assert
- No complex test logic

**Speed:**
- No network I/O (comment: "rodam sem internet")
- No database I/O
- Pure function execution only
- Should complete in milliseconds

## Testing Strategy Observations

**What's Tested:**
1. Text extraction removes unwanted tags (script, nav)
2. Text extraction preserves title
3. Heuristic extractor creates valid Briefing object
4. Heuristic extractor finds company name from title
5. Heuristic extractor finds contact information (email, phone)

**What's NOT Tested:**
1. HTTP fetching logic (`buscar_html()`) - would need mocking
2. Database operations (`db.salvar()`, `db.buscar()`) - would need test DB
3. FastAPI endpoints (`/api/briefings`, `/health`, `/api/historico`)
4. LLMExtractor (not implemented yet)
5. robots.txt checking (`pode_raspar()`)
6. Cache expiration logic

**Testing Approach:**
- Focus on testable, pure functions first
- Test HTML parsing and extraction without network
- Integration tests cover extractor → briefing flow
- Pragmatic: test what matters for business value (briefing generation)

## Future Testing Patterns

**For API Endpoints:**
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
response = client.post("/api/briefings", json={"urls": ["..."], "forcar_atualizacao": False})
assert response.status_code == 200
assert len(response.json()) > 0
```

**For Database Operations:**
```python
# Would need test database or fixtures
import app.db as db

db.salvar("https://test.com", {"empresa": "Test"}, "test")
result = db.buscar("https://test.com")
assert result is not None
```

**For Network Operations:**
```python
# Would need mocking
from unittest.mock import patch, MagicMock
import app.fetcher

with patch('app.fetcher.httpx.Client') as mock_client:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>...</html>"
    # ...
```

---

*Testing analysis: 2026-08-26*
