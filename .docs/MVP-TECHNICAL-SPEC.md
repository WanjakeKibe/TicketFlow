# TicketFlow MVP Technical Specification

## 1. Objective

Deliver a usable, API-first ticketing system for small support teams. A company can create tickets, assign agents, communicate through comments, and move tickets through a controlled lifecycle. Company data must be isolated at the server boundary.

## 2. MVP Scope

### Included

- Company accounts and tenant-scoped users
- Roles: `OWNER`, `MANAGER`, `AGENT`
- Email/password authentication with short-lived access tokens
- Company-scoped API keys for ticket creation
- Ticket CRUD with search, filtering, sorting, and pagination
- Ticket fields: title, description, status, priority, category, requester, assignee
- Comments and immutable ticket activity history
- Agent dashboard for the core workflow
- REST API documentation via OpenAPI
- Automated tests for authentication, authorization, tenant isolation, and lifecycle rules

### Deferred

WhatsApp, SMS, USSD, hosted customer portal, file attachments, outbound webhooks, notifications, duplicate detection, related tickets, and advanced reporting. These should be added only after the core workflow is reliable.

## 3. Technical Choices

- **Backend:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, Alembic
- **Database:** PostgreSQL 16
- **Frontend:** React with TypeScript and Vite
- **Authentication:** Argon2id password hashing and signed bearer tokens
- **Local development:** Docker Compose for PostgreSQL; Redis is optional until background work is introduced
- **Testing:** Pytest and HTTP client integration tests; frontend tests for critical interactions

The backend owns all authorization and business rules. The frontend is a client and must not be treated as a security boundary.

## 4. Core Data Model

- `companies`: tenant identity and timestamps
- `users`: company membership, email, password hash, role, active flag
- `api_keys`: company, key hash, name, last-used timestamp, revoked timestamp
- `customers`: company-scoped requester identity and optional external reference
- `tickets`: company, public ID, title, description, status, priority, category, requester, assignee, timestamps
- `comments`: ticket, author, body, internal flag, timestamps
- `ticket_events`: ticket, actor, event type, previous value, new value, timestamp

Every tenant-owned table includes `company_id`. Queries must require the authenticated company context; repositories must not expose unscoped lookup methods.

## 5. Ticket Rules

Statuses are:

`OPEN -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED`

Allowed exceptions:

- `OPEN -> IN_PROGRESS` when an agent starts work without explicit assignment
- `RESOLVED -> OPEN` when the requester reopens a ticket
- `CLOSED` is terminal for the MVP

Rules:

- Only managers and owners may assign tickets or change priority/category.
- Agents may update tickets assigned to them and add comments.
- Managers and owners may update any ticket in their company.
- All status, assignment, priority, and category changes create a `ticket_event`.
- Every mutation validates the current version or update timestamp to prevent silent overwrites.

## 6. REST API

Base path: `/api/v1`

### Authentication

- `POST /auth/register`
- `POST /auth/login`
- `GET /me`

### Companies and users

- `POST /companies`
- `GET /companies/{company_id}`
- `GET /companies/{company_id}/users`

### Tickets

- `POST /tickets`
- `GET /tickets`
- `GET /tickets/{ticket_id}`
- `PATCH /tickets/{ticket_id}`
- `POST /tickets/{ticket_id}/comments`
- `GET /tickets/{ticket_id}/events`

List endpoints use `page`, `page_size`, `status`, `priority`, `assignee_id`, and `search`. Responses contain `items`, `page`, `page_size`, and `total`.

Errors use a consistent shape:

```json
{
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "Ticket was not found"
  }
}
```

Ticket creation accepts an `Idempotency-Key` header. Repeating a request with the same key returns the original result rather than creating another ticket.

## 7. Authorization and Tenant Isolation

Authentication establishes the user or API-key identity and `company_id`. Each request then applies role permissions and company scope. IDs from another company must return `404`, not reveal whether the resource exists.

Required integration tests:

- Company A cannot read, update, comment on, or list Company B tickets.
- An agent cannot update another agent's unassigned ticket.
- A revoked API key cannot create tickets.
- Users cannot access company administration outside their role.

## 8. Operational Requirements

- Validate all input at the API boundary.
- Store secrets in environment variables, never source control.
- Use structured application logs with request IDs.
- Run database migrations during deployment.
- Add health endpoints for the API and database.
- Record UTC timestamps and use UTC consistently.
- Do not log passwords, bearer tokens, or raw API keys.

## 9. Delivery Order

1. Scaffold backend, frontend, Docker Compose, migrations, and CI.
2. Implement companies, users, authentication, and role checks.
3. Implement tickets, comments, events, and lifecycle validation.
4. Add tenant-isolation and permission integration tests.
5. Build the minimal agent dashboard against the API.
6. Document local setup and API usage in `README.md`.
7. Add the first external intake channel only after the vertical slice passes.

## 10. Definition of Done

A local deployment can register a company, create users, authenticate, create and assign a ticket, add a comment, resolve it, and close it through the API and dashboard. Automated tests prove that authentication, role permissions, lifecycle rules, idempotency, and cross-company access isolation work as specified.
