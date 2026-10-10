# TicketFlow Implementation Roadmap

## 1. Current Baseline

TicketFlow is currently at the initial backend scaffold stage.

Existing:

- FastAPI application in `backend/app/main.py`.
- Root endpoint at `GET /`.
- Application health endpoint at `GET /api/v1/health`.
- Database health endpoint at `GET /api/v1/health/db`.
- Initial SQLAlchemy, PostgreSQL, FastAPI, Pydantic, and Uvicorn dependencies.
- Initial settings, SQLAlchemy base, session dependency, and versioned health router.
- MVP requirements in `.docs/MVP-TECHNICAL-SPEC.md`.

Missing:

- Database configuration and migrations.
- SQLAlchemy models and repositories.
- Authentication and password hashing.
- Role-based authorization.
- Tenant isolation.
- Company, user, customer, ticket, comment, event, and API-key endpoints.
- Ticket lifecycle and optimistic concurrency rules.
- Idempotent ticket creation.
- Automated tests.
- Docker Compose, CI, and operational documentation.
- React/TypeScript frontend and agent dashboard.

The current database engine is initialized lazily so the API can import and
serve non-database routes even when PostgreSQL or its native driver is not
available. The database health endpoint reports connectivity failures when it
is called.

The first cleanup should also standardize the application branding from `Ticketflw` to `TicketFlow`, clarify the application entrypoint, and replace the static health response with an application and database health check.

## 2. Target Architecture

Use the existing package structure and add explicit service and repository layers:

```text
backend/
  app/
    main.py
    api/v1/
      auth.py
      companies.py
      tickets.py
      dependencies.py
    core/
      config.py
      security.py
      permissions.py
      errors.py
      logging.py
    db/
      session.py
      base.py
    models/
      company.py
      user.py
      api_key.py
      customer.py
      ticket.py
      comment.py
      ticket_event.py
      idempotency.py
    schemas/
      auth.py
      company.py
      ticket.py
      comment.py
      common.py
    repositories/
      companies.py
      users.py
      tickets.py
    services/
      auth.py
      companies.py
      tickets.py
```

Responsibilities:

- API routes validate HTTP input and translate service results into responses.
- Dependencies establish authentication and the current company context.
- Services enforce business rules, permissions, lifecycle transitions, events, idempotency, and concurrency.
- Repositories perform company-scoped persistence operations.
- Models define database constraints and relationships.
- Schemas define stable request and response contracts.

Repositories must not expose unscoped tenant-owned lookups. Every repository method should receive `company_id` explicitly or receive a request context that contains it.

## 3. Phase One: Project Foundation

### Deliverables

- Correct API title, description, root response, and package naming.
- Centralized environment configuration with `pydantic-settings`.
- PostgreSQL Docker Compose configuration.
- Alembic setup and initial migration.
- Standard development entrypoint and startup command.
- `/api/v1/health` application health endpoint.
- `/api/v1/health/db` database connectivity check.
- Request ID middleware.
- Structured application logging.
- CORS configuration for local frontend development.
- Pytest configuration and a first smoke test.
- `.env.example` containing non-secret configuration names.

### Acceptance criteria

- A fresh checkout can start the API and PostgreSQL using documented commands.
- Database migrations run successfully against a clean database.
- The API imports and starts from one unambiguous entrypoint.
- Settings are loaded from environment variables.
- Health checks distinguish application health from database health.
- Logs do not contain passwords, bearer tokens, or raw API keys.

### Phase 1 exit criteria

Phase 1 is complete only when every gate below passes from a clean checkout.
Record the commands and results in the handoff notes before moving to Phase 2.

- [ ] `docker compose config` succeeds and the PostgreSQL service is defined
      with non-secret local development credentials.
- [ ] `docker compose up -d postgres` starts PostgreSQL and the container
      reports healthy.
- [ ] The documented dependency installation command succeeds in a fresh
      virtual environment.
- [ ] `alembic upgrade head` succeeds against an empty PostgreSQL database.
- [ ] `python -m uvicorn app.main:app` starts from the documented directory
      without import errors.
- [ ] `GET /` returns the TicketFlow API response.
- [ ] `GET /api/v1/health` returns HTTP 200 with application status.
- [ ] `GET /api/v1/health/db` returns HTTP 200 with database status while
      PostgreSQL is running and a controlled HTTP 503 when it is unavailable.
- [ ] A request ID is present in every application request log.
- [ ] Logs contain no passwords, bearer tokens, API keys, or database secrets.
- [ ] The smoke test suite passes with `pytest`.
- [ ] CORS behavior is verified for the configured local frontend origin.
- [ ] `docker compose down -v` removes the local database and the full setup
      can be repeated successfully.

If any gate fails, Phase 1 remains incomplete. A missing environment prerequisite
must be documented as a blocker rather than counted as a passing result.

## 4. Phase Two: Database Model and Migrations

Implement the following tables:

- `companies`: tenant identity and timestamps.
- `users`: company membership, email, password hash, role, active flag, and timestamps.
- `api_keys`: company, key hash, name, last-used timestamp, and revoked timestamp.
- `customers`: company-scoped requester identity and optional external reference.
- `tickets`: company, public ID, title, description, status, priority, category, requester, assignee, version, and timestamps.
- `comments`: ticket, company, author, body, internal flag, and timestamps.
- `ticket_events`: ticket, company, actor, event type, previous value, new value, and timestamp.
- `idempotency_keys`: company, key, request fingerprint, stored response, ticket ID, and timestamp.

### Database rules

- Every tenant-owned table has a non-null `company_id`.
- Tenant-local uniqueness is enforced with database constraints.
- API key values are hashed and never persisted in raw form.
- Ticket events are append-only.
- Ticket `version` increments on every successful mutation.
- All timestamps are timezone-aware UTC values.
- Foreign keys use explicit deletion behavior.
- Migrations are the only supported way to change the database schema.

### Recommended indexes

- `tickets(company_id, created_at)`.
- `tickets(company_id, status)`.
- `tickets(company_id, priority)`.
- `tickets(company_id, assignee_id)`.
- `tickets(company_id, requester_id)`.
- `idempotency_keys(company_id, key)`.

### Phase 2 exit criteria

Phase 2 is complete only when every gate below passes against a clean
PostgreSQL database. Phase 3 must not begin until the schema is reproducible
and the model constraints are covered by tests.

- [ ] All eight specified SQLAlchemy models exist and are imported into
      `Base.metadata`.
- [ ] Every tenant-owned table has a non-null `company_id` column and an
      explicit foreign key to `companies` where applicable.
- [ ] User roles, ticket statuses, priorities, and event types use defined
      enums rather than unrestricted strings.
- [ ] Tenant-local uniqueness constraints exist for company-scoped emails,
      ticket public IDs, API keys, and idempotency keys.
- [ ] Required foreign keys, indexes, timestamp columns, and ticket version
      columns are present in the generated schema.
- [ ] Ticket events are append-only through the application persistence layer.
- [ ] `alembic upgrade head` creates all Phase 2 tables from an empty database.
- [ ] `alembic downgrade base` removes the Phase 2 schema cleanly.
- [ ] Running `alembic upgrade head` again recreates the complete schema.
- [ ] Alembic autogenerate reports no uncommitted model changes after migration.
- [ ] Integration tests create and retrieve records for every model using
      PostgreSQL.
- [ ] Integration tests reject missing tenant IDs, invalid foreign keys, and
      duplicate tenant-scoped values.
- [ ] Tests prove records from different companies remain distinguishable by
      `company_id` at the persistence boundary.
- [ ] `pytest` passes from a clean database, and the senior-backend migration
      analysis reports no findings.

If any schema, migration, or persistence gate fails, Phase 2 remains
incomplete. Do not compensate for a failed database constraint with frontend
validation or route-only checks.

## 5. Phase Three: Authentication and Tenant Context

### Deliverables

- `POST /api/v1/auth/register`.
- `POST /api/v1/auth/login`.
- `GET /api/v1/me`.
- Argon2id password hashing.
- Short-lived signed bearer access tokens.
- Active-user validation.
- Company-scoped API-key creation and revocation flow.
- API-key last-used tracking.
- Authentication dependency that returns a request identity.

The request identity should contain:

```text
principal_type
user_id or api_key_id
company_id
role, when applicable
```

Company registration should create the company and its owner in one transaction. API keys should be shown only when created; subsequent requests should use the stored hash for verification.

### Acceptance criteria

- Valid credentials return an access token.
- Invalid credentials return a consistent authentication error.
- Inactive users cannot authenticate or use an existing token.
- Revoked API keys cannot create tickets.
- A principal from Company A cannot access Company B resources.
- Authentication failures do not reveal whether an email exists.

### Phase 3 exit criteria

Phase 3 is complete only when every gate below passes. Record the commands
and results in the handoff notes before moving to Phase 4.

- [x] Company registration creates the company and owner in one transaction.
- [x] Valid credentials return a short-lived signed bearer access token.
- [x] Invalid credentials return the same authentication error without
      revealing whether an email exists.
- [x] `GET /api/v1/me` returns the current active user.
- [x] Passwords are hashed with Argon2id and are never stored or logged in
      plaintext.
- [x] Inactive users cannot authenticate or use an existing token.
- [x] The authenticated request identity contains principal type, principal
      ID, company ID, and role when applicable.
- [x] Owners can create and revoke company-scoped API keys.
- [x] Raw API keys are shown only at creation and only hashes are persisted.
- [x] API-key authentication updates `last_used_at`.
- [x] Revoked API keys are rejected by the API-key authentication dependency.
- [x] Forged user tokens cannot cross company boundaries.
- [x] Focused Phase 3 tests pass with `python -m pytest -q tests/test_auth.py`.
- [x] Full backend tests pass with `python -m pytest -q` against the supported
      PostgreSQL test environment (`16 passed`, 1 existing deprecation warning).

If any gate fails, Phase 3 remains incomplete. The full ticket API is not yet
available, so revoked-key ticket-creation behavior must be verified again when
the ticket creation endpoint is implemented in Phase 5.

## 6. Phase Four: Company Administration and Authorization

Implement:

- `POST /api/v1/companies`.
- `GET /api/v1/companies/{company_id}`.
- `GET /api/v1/companies/{company_id}/users`.

Roles:

- `OWNER`: full company administration and ticket access.
- `MANAGER`: operational ticket management across the company.
- `AGENT`: assigned-ticket workflow and permitted comments.

Authorization rules:

- Owners can administer their company.
- Managers can manage operational ticket work but cannot perform owner-only actions.
- Agents can access only permitted ticket workflows.
- Cross-company resources return `404`, not `403`, to avoid leaking existence.
- Same-company forbidden actions return `403`.

Centralize these checks in reusable permission dependencies or service helpers. Do not duplicate role comparisons in route handlers.

### Phase 4 exit criteria

Phase 4 is complete only when every gate below passes:

- [x] `POST /api/v1/companies` creates a company and owner atomically and
      returns the owner access token.
- [x] `GET /api/v1/companies/{company_id}` returns the authenticated company
      and hides cross-company IDs with `404`.
- [x] `GET /api/v1/companies/{company_id}/users` is tenant-scoped and returns
      users in deterministic creation order.
- [x] Owners and managers can list users in their company.
- [x] Agents receive `403` for same-company user administration.
- [x] Cross-company user-list requests return `404` before role evaluation.
- [x] Owner-only API-key operations reject managers with `403`.
- [x] Role checks are centralized in reusable dependency/service helpers.
- [x] Focused Phase 4 tests pass with
      `python -m pytest -q tests/test_auth.py tests/test_companies.py`
      (`9 passed`, 1 existing deprecation warning).
- [ ] Full backend tests pass with `python -m pytest -q` against PostgreSQL.
      PostgreSQL was unavailable in the local Docker daemon during this
      verification attempt.

If the PostgreSQL gate is unavailable, Phase 4 remains pending final
database-backed verification even when the focused suite passes.

## 7. Phase Five: Ticket CRUD Vertical Slice

Implement:

- `POST /api/v1/tickets`.
- `GET /api/v1/tickets`.
- `GET /api/v1/tickets/{ticket_id}`.
- `PATCH /api/v1/tickets/{ticket_id}`.

Ticket fields:

- Title.
- Description.
- Status.
- Priority.
- Category.
- Requester.
- Assignee.
- Created and updated timestamps.
- Current version.

List endpoints must support:

- `page`.
- `page_size`.
- `status`.
- `priority`.
- `assignee_id`.
- `search`.
- Deterministic sorting.

List responses must contain:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

Use a service entrypoint such as `update_ticket(company_id, ticket_id, patch, expected_version, actor)` so authorization and concurrency checks cannot be bypassed.

### Phase 5 exit criteria

Phase 5 is complete only when every gate below passes:

- [x] `POST /api/v1/tickets` creates a ticket for an existing
      company-scoped requester.
- [x] Ticket creation accepts bearer users and active company API keys.
- [x] Revoked API keys cannot create tickets.
- [x] `GET /api/v1/tickets/{ticket_id}` returns only tickets in the
      authenticated company.
- [x] `GET /api/v1/tickets` supports page, page size, status, priority,
      assignee, search, and deterministic sorting.
- [x] `PATCH /api/v1/tickets/{ticket_id}` requires the expected ticket version
      and returns `409` for stale updates.
- [x] Managers and owners can update company tickets.
- [x] Agents can update assigned tickets but cannot change assignment,
      requester, priority, or category.
- [x] Cross-company ticket IDs return `404`.
- [x] Ticket API behavior is implemented through a service entrypoint so
      tenant and authorization checks are not bypassed by route handlers.
- [x] Focused Phase 5 tests pass with
      `python -m pytest -q tests/test_auth.py tests/test_companies.py tests/test_tickets.py`
      (`14 passed`, 1 existing deprecation warning).
- [ ] Full backend tests pass with `python -m pytest -q` against PostgreSQL.
      PostgreSQL verification remains pending when Docker Desktop is
      unavailable.

## 8. Phase Six: Lifecycle, Comments, and Activity History

Allowed status transitions:

```text
OPEN -> ASSIGNED
OPEN -> IN_PROGRESS
ASSIGNED -> IN_PROGRESS
IN_PROGRESS -> RESOLVED
RESOLVED -> CLOSED
RESOLVED -> OPEN
```

Rules:

- `CLOSED` is terminal.
- `OPEN -> IN_PROGRESS` is allowed when an agent starts without explicit assignment.
- Only managers and owners may assign tickets.
- Only managers and owners may change priority or category.
- Agents may update tickets assigned to them.
- Managers and owners may update any company ticket.
- Status, assignment, priority, and category changes create ticket events.
- Every mutation checks the expected ticket version.

Implement:

- `POST /api/v1/tickets/{ticket_id}/comments`.
- `GET /api/v1/tickets/{ticket_id}/events`.

Events must be created in the same transaction as the ticket mutation and must not be editable or deletable through the API.

### Phase 6 exit criteria

Phase 6 is complete only when every gate below passes:

- [x] Ticket updates enforce the allowed lifecycle transitions and terminal
      `CLOSED` state.
- [x] Status, assignment, priority, and category changes create immutable
      ticket events in the same transaction as the update.
- [x] `POST /api/v1/tickets/{ticket_id}/comments` requires the expected ticket
      version, persists the comment and event atomically, and increments the
      ticket version.
- [x] `GET /api/v1/tickets/{ticket_id}/events` is tenant-scoped and returns
      immutable activity history.
- [x] Cross-company ticket IDs return `404` for comments and events.
- [x] Focused ticket tests pass with
      `python -m pytest -q tests/test_tickets.py`.
- [ ] Full backend tests pass with `python -m pytest -q` against PostgreSQL.
      PostgreSQL verification remains pending when Docker Desktop is
      unavailable.

## 9. Phase Seven: Idempotency and Concurrency

Ticket creation accepts the `Idempotency-Key` header.

Required behavior:

- Repeating the same key for the same company and equivalent request returns the original response.
- Reusing a key with a different request returns a conflict.
- The same key can be used independently by different companies.
- Concurrent duplicate requests create only one ticket.
- Stored responses preserve the original status and response body.

For updates, use an integer ticket version. Clients submit the version they read; updates with a stale version return a conflict instead of silently overwriting newer data.

## 10. Phase Eight: Error Contract and OpenAPI

All API errors should use this shape:

```json
{
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "Ticket was not found"
  }
}
```

Define stable codes for:

- Authentication failures.
- Authorization failures.
- Validation failures.
- Missing resources.
- Invalid lifecycle transitions.
- Stale ticket versions.
- Idempotency conflicts.
- Revoked API keys.

Document request bodies, response bodies, authentication requirements, error responses, pagination, filters, and examples in the generated OpenAPI schema.

## 11. Testing Plan

Build tests alongside each implementation phase.

### Authentication and authorization

- Registration creates a company and owner.
- Login succeeds and fails correctly.
- Inactive users are rejected.
- Owners, managers, and agents receive the correct permissions.
- Users cannot access another company.
- Cross-company resource IDs return `404`.
- Revoked API keys cannot create tickets.

### Ticket behavior

- Ticket creation and retrieval are company-scoped.
- Listing supports pagination, filtering, search, and sorting.
- Agents cannot update unassigned or differently assigned tickets.
- Managers and owners can update company tickets.
- Valid transitions succeed.
- Invalid transitions fail.
- Closed tickets remain terminal.
- Events are created for required field changes.
- Events cannot be modified or deleted.
- Comments are company-scoped.

### Concurrency and idempotency

- Duplicate idempotency requests return one ticket.
- Conflicting requests using one key fail.
- Different companies can use the same key independently.
- Stale ticket versions fail without changing the newer record.

Use isolated test databases, factories, and integration tests through FastAPI's HTTP client. Tenant-isolation tests are release blockers.

## 12. Phase Nine: Agent Dashboard

Start the frontend after the authenticated ticket API vertical slice is stable.

Create a React, TypeScript, and Vite application with:

- Login and registration.
- Authenticated route handling.
- Ticket list with filtering and pagination.
- Ticket detail view.
- Assignment and status controls.
- Comment timeline.
- Activity history.
- Permission-aware controls.
- Loading, empty, validation, unauthorized, and server-error states.
- API client support for bearer tokens and the standard error format.

The backend remains authoritative. Frontend control visibility is a usability feature, not a security boundary.

## 13. Phase Ten: Operations and Documentation

Add:

- Docker Compose development workflow.
- `.env.example`.
- CI for formatting, linting, type checking, migrations, and tests.
- Deployment migration command.
- API and database health checks.
- Development seed or bootstrap commands.
- Secure CORS and token-expiration defaults.
- README setup instructions.
- API usage examples.
- Troubleshooting notes for database and migration failures.

## 14. Delivery Milestones

1. Foundation, configuration, Docker, migrations, and health checks.
2. Companies, users, password hashing, login, bearer tokens, and tenant context.
3. Ticket creation and company-scoped ticket listing.
4. Ticket detail, updates, permissions, lifecycle validation, and events.
5. Comments, idempotency, and optimistic concurrency.
6. Integration test suite and OpenAPI contract cleanup.
7. React agent dashboard.
8. CI, documentation, deployment checks, and MVP review.

## 15. MVP Release Criteria

The MVP is ready when a local deployment can:

1. Register a company and owner.
2. Authenticate the owner.
3. Create users with appropriate roles.
4. Create a ticket.
5. Assign the ticket.
6. Move it through the supported lifecycle.
7. Add a comment.
8. Inspect immutable activity events.
9. Reject stale updates.
10. Return the original result for duplicate ticket creation requests.
11. Prevent another company from reading or changing the ticket.
12. Complete the same workflow through the dashboard.

All required automated tests must pass, migrations must work from an empty database, and the README must document local setup and API usage.
