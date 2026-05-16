# ProbePilot — Sprint 4 Changes

## Summary

Sprint 4 adds operational depth (database migrations, a real health probe) and monitoring flexibility (endpoint enable/disable, custom HTTP method/headers/body, check-history filtering, endpoint search). All work is additive; no client breakage except the richer `/health` response shape.

## Migrations

Schema is now managed by **Alembic**. The FastAPI lifespan invokes `command.upgrade(Config("alembic.ini"), "head")` on startup, so a fresh local install gets a working DB with no manual step. `Base.metadata.create_all` is no longer called by the application — tests still use it on the in-memory engine inside `tests/conftest.py`.

Migrations introduced this sprint (`alembic/versions/`), in chain order — a
single linear graph with one head (`d38850925cbc`):

| Order | Revision | Description |
|---|---|---|
| 1 | `d437eb92d569_baseline_schema` | Creates `endpoints`, `checks`, `incidents`, plus the unique partial index `uq_open_incident_endpoint` on `(endpoint_id) WHERE status='open'`. |
| 2 | `b29b7304d1ba_add_method_headers_body_to_endpoints` | Adds `endpoints.method TEXT DEFAULT 'GET'`, `endpoints.request_headers JSON`, `endpoints.request_body TEXT`. |
| 3 | `d38850925cbc_add_enabled_to_endpoints` | Adds `endpoints.enabled BOOLEAN NOT NULL DEFAULT 1`. |

> Note: `b29b7304d1ba` first shipped (PR #9) with `down_revision=None`, which
> split the graph into two heads and made `alembic upgrade head` fail on a
> fresh DB. Fixed in PR #10 (`down_revision = d437eb92d569`). Guarded now by
> `tests/test_migrations.py::test_single_alembic_head` and a blocking
> ForgeLoop "Migrations (alembic upgrade head)" check.

Commands:
- Apply latest: `uv run alembic upgrade head`
- Create new migration: `uv run alembic revision --autogenerate -m "..."`
- Stamp without running (for an existing DB that already has the schema): `uv run alembic stamp head`

The migration URL is read from the `PROBEPILOT_DATABASE_URL` env var inside `alembic/env.py` (default `sqlite:///./probepilot.db`).

## API additions and changes

### `GET /health` — shape changed

Before:
```json
{ "status": "healthy" }
```

After:
```json
{
  "status": "healthy" | "degraded",
  "version": "0.1.0",
  "db": "ok" | "error",
  "error": null | "<short message>"
}
```

The route always returns HTTP 200 (so an external probe gets the shape even in `degraded`). `version` is read once at import from `pyproject.toml` via stdlib `tomllib`. `db` is determined by `SELECT 1`.

### Endpoint resource — new fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `enabled` | `bool` | `true` | When `false`, manual checks are rejected (see below). |
| `method` | `"GET" \| "POST" \| "HEAD" \| "PUT" \| "DELETE" \| "PATCH"` | `"GET"` | HTTP method used by manual checks. |
| `request_headers` | `dict[str, str] \| null` | `null` | Forwarded on the outbound HTTP call. |
| `request_body` | `string \| null` | `null` | Forwarded as the outbound request body. |

Reflected in `EndpointCreate`, `EndpointUpdate`, and `EndpointResponse`.

### `PUT` and `PATCH /endpoints/{id}` — partial update

Both routes accept an `EndpointUpdate` body and apply a partial update via a
shared helper: only fields present in the request are changed (including
`enabled`). `PUT` was the existing route; `PATCH` was added as a semantic
alias for clients that distinguish it.

### `POST /endpoints/{id}/checks` — new behaviour

- Returns **HTTP 409** with `{"detail": "Endpoint is disabled", "code": "endpoint_disabled"}` when the endpoint has `enabled=false`.
- Uses the endpoint's `method`, `request_headers`, and `request_body` when invoking the outbound HTTP call (was previously hard-coded `GET`).

### `GET /endpoints/{id}/checks` — new query params

Combinable with the existing `limit` / `offset`:

- `success: bool` — filter to passing or failing checks.
- `since: datetime` (RFC 3339) — only checks whose `checked_at >= since`.
- `until: datetime` (RFC 3339) — only checks whose `checked_at <= until`.

`meta.total` reflects the filtered set, not the unfiltered total.

### `GET /endpoints` — new query param

- `q: string` — case-insensitive substring match against `name` or `url`. Combinable with `limit` / `offset`.

## Configuration

- `PROBEPILOT_DATABASE_URL` (unchanged) — now also consumed by `alembic/env.py`.

## Upgrade walkthrough (Sprint 3 → Sprint 4)

1. Pull the sprint-4 branch.
2. `uv sync` — installs Alembic into the dev group.
3. **If you have an existing local `probepilot.db` from Sprint 3 (no `alembic_version` table):**
   - Easiest for dev: delete `probepilot.db` and let the lifespan recreate it via `alembic upgrade head` on next start.
   - Preserve data: `uv run alembic stamp d437eb92d569`, then `uv run alembic upgrade head`.
4. Existing client code that consumes `GET /endpoints`, `GET /endpoints/{id}/checks`, `GET /endpoints/{id}/incidents` keeps working — the Page envelope is unchanged; new optional query params are additive.
5. **If your client scripts the `/health` endpoint, update it** to read the new fields (`version`, `db`, `error`). Health probes that only check the HTTP status code keep working.

## Out of scope this sprint (unchanged)

Auth, scheduler, cloud deployment, Docker, frontend, metrics export, alerting integrations.

## QA gate (final)

ForgeLoop checks green on `main` after PR #10 (which re-delivered S4-3 and
fixed the migration chain):

| Check | Conclusion |
|---|---|
| Lint (ruff) | ✅ |
| Migrations (alembic upgrade head) | ✅ (blocking; added after PR #9) |
| Tests (pytest) | ✅ 78 passing |
| Coverage | ✅ ≥85% (gate enforced) |
| Bandit | ✅ |
| pip-audit | ✅ no known CVEs |
| mypy | ✅ 0 errors / 21 files |

## ForgeLoop driving record

- Requirement `75cb2806-fde4-4393-b6c6-95e02326e3ca` analyzed and decomposed by deepseek.
- 8 dev_tasks (S4-1 … S4-8). Each passed the ForgeLoop QA gate individually.
- S4-1/2/4/5/6/7/8 shipped via the Sprint 4 integration (PR #9). The manual
  file-level merge of the parallel DT branches **silently dropped S4-3**
  (endpoint enable/disable); it was re-delivered as its own reviewed PR
  (#10), which also fixed the `b29b7304d1ba` migration-chain bug above.
- This integration-drop is why the project moved to one PR per dev_task
  going forward (manual multi-branch integration is too fragile).
