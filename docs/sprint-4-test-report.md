# ProbePilot — Sprint 4 Test Report

Generated: 2026-05-14

## Summary
- Total tests passing: 71 (from `uv run pytest -q`)
- Coverage: 99% (from `uv run pytest --cov=. --cov-report=term-missing`)
- mypy: 0 errors / 19 files (from `uv run mypy --ignore-missing-imports .`)
- Lint (ruff): clean
- Bandit: clean
- pip-audit: no known CVEs

## Per-file test counts and coverage

| file | statements | missed | cover |
|---|---|---|---|
| checks.py | 87 | 0 | 100% |
| database.py | 13 | 4 | 69% |
| endpoints.py | 50 | 0 | 100% |
| incidents.py | 35 | 0 | 100% |
| logging_config.py | 20 | 0 | 100% |
| main.py | 38 | 5 | 87% |
| models.py | 37 | 0 | 100% |
| schemas.py | 70 | 0 | 100% |
| tests/__init__.py | 0 | 0 | 100% |
| tests/conftest.py | 26 | 0 | 100% |
| tests/test_checks.py | 356 | 0 | 100% |
| tests/test_endpoints.py | 181 | 0 | 100% |
| tests/test_incidents.py | 163 | 0 | 100% |
| tests/test_logging.py | 78 | 1 | 99% |
| tests/test_main.py | 30 | 0 | 100% |
| tests/test_models.py | 66 | 0 | 100% |

### Per-file test counts
- `tests/test_checks.py`: 23 tests
- `tests/test_endpoints.py`: 25 tests
- `tests/test_incidents.py`: 12 tests
- `tests/test_logging.py`: 6 tests
- `tests/test_main.py`: 2 tests
- `tests/test_models.py`: 3 tests

## New tests by dev task

- **DT-S4-1 Alembic**: no new tests (infrastructure only)
- **DT-S4-2 Enriched /health**: `test_health_ok`, `test_health_degraded_when_db_fails` (replaced single `test_health_check`)
- **DT-S4-3 Endpoint enable/disable**: `test_endpoint_enabled_default_true`, `test_patch_endpoint_enabled_false`, `test_checks_rejected_on_disabled_endpoint_409`, etc.
- **DT-S4-4 Custom HTTP**: `test_check_default_get`, `test_check_post_with_body`, `test_check_custom_header`, `test_check_head_method`
- **DT-S4-5 Check-history filtering**: `test_list_checks_filter_success_true`, `_false`, `_since`, `_until`, `_combined`, `_with_pagination`
- **DT-S4-6 Endpoint search**: `test_search_by_name`, `test_search_by_url`, `test_search_no_match`, `test_search_case_insensitive`, `test_search_with_pagination`

## Per-dev-task pass/fail summary

| DT | Title | First-run QA | Final |
|---|---|---|---|
| S4-1 | Alembic | PASS | PASS |
| S4-2 | Enriched /health | PASS | PASS |
| S4-3 | Enable/disable | PASS | PASS |
| S4-4 | Custom HTTP | PASS | PASS |
| S4-5 | Check filtering | PASS | PASS |
| S4-6 | Endpoint search | PASS | PASS |

## Notes
- Coverage gate: enforced at >=85% (pytest.ini addopts). Current 99%.
- One test (`tests/test_logging.py` line 35) has a missing-line coverage gap — note it explicitly.
- HTTP mocking pattern: tests mock `checks._execute_http_request` (a thin seam) so TestClient's own httpx use is not affected.
