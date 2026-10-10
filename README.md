# TicketFlow

TicketFlow is an API-first, multi-tenant ticketing system for small support
teams. The backend is built with FastAPI, SQLAlchemy, PostgreSQL, and Pydantic.

This README is the shared starting point for everyone working on the project.
Keep setup commands, supported behavior, and known limitations documented here
when they change.

## Current Status

The repository currently contains the backend foundation through the Phase 7
idempotency and concurrency slice:

- FastAPI application and versioned API routing.
- Environment-based application settings.
- SQLAlchemy engine and session configuration.
- Application and database health endpoints.
- Authentication, tenant-bound identities, and API-key lifecycle support.
- Tenant-scoped company retrieval and role-protected company user listing.
- Tenant-scoped ticket creation, retrieval, filtering, pagination, and updates.
- Controlled ticket lifecycle transitions, optimistic concurrency for comments,
  and immutable ticket activity events.
- Company-scoped ticket creation idempotency with replay and conflict handling.
- MVP requirements and implementation roadmap.

The frontend remains planned work. See
[ROADMAP.md](ROADMAP.md) and
[.docs/MVP-TECHNICAL-SPEC.md](.docs/MVP-TECHNICAL-SPEC.md) for the target scope.

## Quick Start

From PowerShell at the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

If the virtual environment already exists, activate it and install the
requirements again only when dependencies change.

## Start PostgreSQL

Docker Desktop must be installed and running. From the repository root:

```powershell
docker compose up -d postgres
docker compose ps
```

The PostgreSQL container uses the local development values from
`docker-compose.yml`. These credentials are for local development only.

Stop and remove the local database with:

```powershell
docker compose down -v
```

## Run the Backend

Change to the backend directory before starting Uvicorn. This ensures the
`app` package is resolved correctly and that `.env` is loaded from the backend
directory.

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API is available at http://127.0.0.1:8000.

Stop the server with `Ctrl+C`. The `--reload` option is intended for local
development and restarts the server when backend files change.

## Available Endpoints

| Endpoint                | Purpose                           |
| ----------------------- | --------------------------------- |
| `GET /`                 | API welcome response              |
| `GET /api/v1/health`    | Application health check          |
| `GET /api/v1/health/db` | PostgreSQL connectivity check     |
| `POST /api/v1/auth/register` | Register a company owner       |
| `POST /api/v1/auth/login` | Authenticate and receive a bearer token |
| `GET /api/v1/me` | Get the authenticated user                   |
| `POST /api/v1/auth/api-keys` | Create an owner-managed API key     |
| `DELETE /api/v1/auth/api-keys/{id}` | Revoke an API key              |
| `POST /api/v1/companies` | Register a company and owner       |
| `GET /api/v1/companies/{company_id}` | Get the authenticated company |
| `GET /api/v1/companies/{company_id}/users` | List company users for owners and managers |
| `POST /api/v1/tickets` | Create a company ticket; optionally replay with `Idempotency-Key` |
| `GET /api/v1/tickets` | List company tickets with filters and pagination |
| `GET /api/v1/tickets/{ticket_id}` | Get a company ticket |
| `PATCH /api/v1/tickets/{ticket_id}` | Update a ticket with an expected version |
| `POST /api/v1/tickets/{ticket_id}/comments` | Add a ticket comment with an expected version |
| `GET /api/v1/tickets/{ticket_id}/events` | Get immutable ticket activity history |
| `GET /docs`             | Interactive Swagger documentation |
| `GET /openapi.json`     | OpenAPI document                  |

## Configuration

Settings are loaded from environment variables and an optional `backend/.env`
file. The default database URL uses the pure-Python `pg8000` driver:

```text
postgresql+pg8000://ticketflow:ticketflow@localhost:5433/ticketflow
```

To use a different database, create `backend/.env`:

```env
DATABASE_URL=postgresql+pg8000://username:password@localhost:5433/ticketflow
ENVIRONMENT=development
SQL_ECHO=false
JWT_SECRET_KEY=replace-with-at-least-32-random-characters
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

PostgreSQL must be running before `/api/v1/health/db` can return a healthy
response. `pg8000` is used here to avoid the blocked native `psycopg2` DLL on
Windows. `JWT_SECRET_KEY` must be a stable, randomly generated secret outside
local development. Passwords use Argon2id, and raw API keys are shown only
when they are created; only their hashes are stored.

## Migrations

Run migrations from the `backend` directory after PostgreSQL is running:

```powershell
cd backend
python -m alembic upgrade head
```

The current migrations create the Phase 2 domain tables. Run the migration
command after starting PostgreSQL and before executing database-backed tests.

## Development Checks

Run these commands from `backend` with the virtual environment activated:

```powershell
python -m compileall -q app
python -c "from app.main import app; print(sorted(app.openapi()['paths']))"
python -m pytest -q
python -m pytest -q tests/test_auth.py
python -m pytest -q tests/test_auth.py tests/test_companies.py
```

Run these checks before handing work to the other collaborator. Include any
environment-specific failure, such as a missing PostgreSQL service or blocked
native driver, in the handoff message.

## Collaboration Workflow

Before starting work:

1. Pull or fetch the latest changes.
2. Read [roadmap.md](roadmap.md) and the relevant section of
   [.docs/MVP-TECHNICAL-SPEC.md](.docs/MVP-TECHNICAL-SPEC.md).
3. Confirm the backend starts and the health endpoint responds.

While working:

- Keep changes focused on one feature or fix.
- Preserve the existing FastAPI, SQLAlchemy, and package structure.
- Keep authorization and tenant-isolation rules in backend code.
- Add or update tests with behavior changes.
- Do not commit `.env`, passwords, tokens, database dumps, or virtual environments.
- Update this README when setup commands or supported endpoints change.

Before handing work over:

- Explain what changed and which files own the behavior.
- List commands used to validate the change.
- Mention tests that were not run and any environment prerequisites.
- Leave the worktree in a state the other collaborator can run from a clean checkout.

## Handoff Notes

The current implementation includes authentication, tenant-scoped company
administration, role checks, ticket CRUD, lifecycle validation, comments, and
immutable activity events. Ticket creation requires an existing company-scoped
`requester_id`. Comment creation requires the current ticket `version` and
increments it after the comment and event are persisted in one transaction.
Idempotency and the frontend dashboard are not available yet.
The full backend suite requires the local PostgreSQL service; focused API tests
can run with the SQLite test fixtures.

## Project Layout

```text
TicketFlow/
	backend/
		app/
			api/v1/       Versioned API routes
			core/         Settings and cross-cutting services
			db/           SQLAlchemy base and sessions
			models/       Persistence models
			schemas/      Pydantic API schemas
			main.py       FastAPI application
	.docs/            Product and technical specifications
	ROADMAP.md        Implementation roadmap and exit criteria
	docker-compose.yml Local PostgreSQL service
```
