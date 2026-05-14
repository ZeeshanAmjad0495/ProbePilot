# ProbePilot

ProbePilot is a local-first endpoint monitoring tool built with FastAPI + SQLAlchemy. Register HTTP endpoints, trigger manual health checks, and track incidents automatically when consecutive failures are detected.

## Quickstart

1. Clone the repo and install dependencies:

   ```bash
   uv sync
   ```

2. Start the server:

   ```bash
   uv run uvicorn main:app --reload
   ```

3. Walk through the API with curl:

   **Create an endpoint**

   ```bash
   curl -s -X POST http://localhost:8000/endpoints \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Example API",
       "url": "https://httpbin.org/status/200",
       "expected_status_code": 200,
       "timeout_seconds": 5.0
     }' | jq .
   ```

   ```json
   {
     "id": 1,
     "name": "Example API",
     "url": "https://httpbin.org/status/200",
     "expected_status_code": 200,
     "timeout_seconds": 5.0,
     "created_at": "2026-05-14T08:30:00"
   }
   ```

   **List endpoints**

   ```bash
   curl -s http://localhost:8000/endpoints | jq .
   ```

   Responses are paginated with the shape `{items, meta}`:

   ```json
   {
     "items": [
       {
         "id": 1,
         "name": "Example API",
         "url": "https://httpbin.org/status/200",
         "expected_status_code": 200,
         "timeout_seconds": 5.0,
         "created_at": "2026-05-14T08:30:00"
       }
     ],
     "meta": {
       "total": 1,
       "limit": 50,
       "offset": 0
     }
   }
   ```

   **Trigger a manual check**

   ```bash
   curl -s -X POST http://localhost:8000/endpoints/1/checks | jq .
   ```

   ```json
   {
     "id": 1,
     "endpoint_id": 1,
     "url": "https://httpbin.org/status/200",
     "expected_status_code": 200,
     "actual_status_code": 200,
     "response_time_ms": 234,
     "success": true,
     "error_message": null,
     "checked_at": "2026-05-14T08:31:00"
   }
   ```

   **List check history**

   ```bash
   curl -s http://localhost:8000/endpoints/1/checks | jq .
   ```

   Paginated the same way as endpoints:

   ```json
   {
     "items": [
       {
         "id": 1,
         "endpoint_id": 1,
         "url": "https://httpbin.org/status/200",
         "expected_status_code": 200,
         "actual_status_code": 200,
         "response_time_ms": 234,
         "success": true,
         "error_message": null,
         "checked_at": "2026-05-14T08:31:00"
       }
     ],
     "meta": {
       "total": 1,
       "limit": 50,
       "offset": 0
     }
   }
   ```

   **Open an incident**

   Three consecutive failing checks automatically open an `Incident` for the endpoint. You can simulate this by registering an endpoint that returns a non-expected status code (or is unreachable) and running three checks against it.

   **List incidents**

   ```bash
   curl -s http://localhost:8000/endpoints/1/incidents | jq .
   ```

   ```json
   {
     "items": [
       {
         "id": 1,
         "endpoint_id": 1,
         "title": "Endpoint failure detected",
         "status": "open",
         "failure_count": 3,
         "created_at": "2026-05-14T08:35:00",
         "updated_at": "2026-05-14T08:35:00",
         "resolved_at": null
       }
     ],
     "meta": {
       "total": 1,
       "limit": 50,
       "offset": 0
     }
   }
   ```

   **Resolve an incident**

   ```bash
   curl -s -X POST http://localhost:8000/incidents/1/resolve | jq .
   ```

   ```json
   {
     "id": 1,
     "endpoint_id": 1,
     "title": "Endpoint failure detected",
     "status": "resolved",
     "failure_count": 3,
     "created_at": "2026-05-14T08:35:00",
     "updated_at": "2026-05-14T08:36:00",
     "resolved_at": "2026-05-14T08:36:00"
   }
   ```

   **Delete an endpoint**

   ```bash
   curl -s -X DELETE http://localhost:8000/endpoints/1
   ```

   Returns `204 No Content`. Deletion cascades to all related checks and incidents.

## Configuration

- `PROBEPILOT_DATABASE_URL` — SQLAlchemy database URL. Defaults to `sqlite:///./probepilot.db`. Any SQLAlchemy-compatible URL works (for example, `postgresql+psycopg://...` if you add Postgres dependencies later).

## Migrations

ProbePilot uses Alembic for schema migrations. On startup, the application automatically applies pending migrations.

Apply migrations manually:

```bash
uv run alembic upgrade head
```

Generate a new migration after changing models:

```bash
uv run alembic revision --autogenerate -m "describe your change"
```

## Run tests

```bash
uv run pytest -q
```

Coverage gate is enforced at >= 85%.

## Logs

ProbePilot emits structured JSON logs to stdout. Each log line includes `timestamp`, `level`, `logger`, `message`, and contextual fields. Key event names you will see in the output are:

- `check_executed` — a check completed (includes `success` and `response_time_ms`).
- `incident_opened` — a new incident was created after three consecutive failures.
- `incident_failure_count_incremented` — additional failures accumulated on an already-open incident.
- `incident_resolved_auto` — an incident was closed automatically because a check succeeded.
- `incident_resolved_manual` — an incident was closed via the `POST /incidents/{id}/resolve` endpoint.