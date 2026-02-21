# Inventory Service — Technical Documentation

## Overview

The Inventory Service is the third microservice in the FastAPI Microservices project. It manages product stock levels using PostgreSQL as its database. It is called synchronously by the Order Service before confirming any order to verify stock availability.

---

## Tech Stack Decisions

### PostgreSQL over MongoDB
Inventory data is relational and transactional by nature. Stock quantities must be accurate — if two orders come in simultaneously for the last item, exactly one should succeed. PostgreSQL's ACID guarantees and row-level locking handle this correctly. MongoDB's eventual consistency model is not appropriate here.

### SQLAlchemy (async) over raw SQL
SQLAlchemy provides an ORM that maps Python classes directly to database tables. This eliminates writing raw SQL for common operations, provides type safety, and handles migrations cleanly via Alembic. The async version (`sqlalchemy.ext.asyncio`) works natively with FastAPI's async event loop.

### asyncpg over psycopg2
`asyncpg` is a pure async PostgreSQL driver built for performance. `psycopg2` is synchronous and would block the event loop on every database call. Since FastAPI is async, `asyncpg` is the correct choice.

### Alembic for Migrations
For local development we use `Base.metadata.create_all()` at startup to auto-create tables. In production, Alembic handles schema migrations with versioned migration scripts, allowing safe schema changes without data loss.

### `available_qty` as a computed property
Rather than storing `available_qty` as a separate column that could go out of sync, it is computed as a Python property: `quantity - reserved_qty`. This guarantees consistency without needing triggers or application-level sync logic.

---

## Project Structure

```
inventory-service/
├── app/
│   ├── main.py                      # FastAPI app, lifespan, table creation
│   ├── config.py                    # Settings from .env via pydantic-settings
│   ├── database.py                  # SQLAlchemy async engine, session factory
│   ├── models/
│   │   └── inventory.py             # SQLAlchemy ORM table definition
│   ├── schemas/
│   │   └── inventory.py             # Pydantic request/response schemas
│   ├── routes/
│   │   └── inventory_routes.py      # API endpoint definitions
│   └── services/
│       └── inventory_service.py     # Business logic and DB operations
├── Dockerfile
└── requirements.txt
```

---

## Database Schema

```sql
Table: inventory
┌─────────────────┬──────────────┬────────────────────────────────────┐
│ id (UUID, PK)   │ product_id   │ product_name                       │
│ quantity        │ reserved_qty │ created_at                         │
│ updated_at      │              │                                    │
└─────────────────┴──────────────┴────────────────────────────────────┘

Computed: available_qty = quantity - reserved_qty
Index: product_id (unique)
```

**Why UUID primary key?**
UUIDs are globally unique across services and databases. When microservices share data or merge datasets, integer IDs from different services would collide. UUIDs eliminate this problem entirely.

**Why `reserved_qty`?**
When an order is placed but not yet fulfilled, stock should be reserved so it is not oversold. `reserved_qty` tracks items held for pending orders. `available_qty = quantity - reserved_qty` reflects what is actually available to new orders.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/inventory` | Add a new product to inventory |
| `GET` | `/api/inventory` | List all inventory items |
| `GET` | `/api/inventory/{product_id}` | Get inventory for a specific product |
| `GET` | `/api/inventory/{product_id}/check?quantity=N` | Check if N units are available |
| `PATCH` | `/api/inventory/{product_id}/reduce` | Reduce stock (order placed) |
| `PATCH` | `/api/inventory/{product_id}/restock` | Add stock (new shipment) |
| `PUT` | `/api/inventory/{product_id}` | Update product name or quantity |
| `DELETE` | `/api/inventory/{product_id}` | Remove product from inventory |
| `GET` | `/health` | Health check |

### Key Endpoint — `/check`
This endpoint is specifically designed for the Order Service to call before confirming an order:
```
Order Service → GET /api/inventory/prod-001/check?quantity=2
              ← {"product_id": "prod-001", "requested": 2, "in_stock": true}
```
It returns a boolean `in_stock` field rather than raising an error, so the Order Service can handle insufficient stock gracefully with a proper user-facing message.

---

## How It Differs from Product Service

| Aspect | Product Service | Inventory Service |
|---|---|---|
| Database | MongoDB | PostgreSQL |
| Driver | Motor (async) | asyncpg + SQLAlchemy |
| Models | Not needed (dicts) | SQLAlchemy ORM classes |
| Schema changes | Schemaless, flexible | Alembic migrations |
| ID format | MongoDB ObjectId | UUID |
| Transactions | Not used | ACID via PostgreSQL |

---

## Issues Encountered and Fixes

### Issue 1 — `greenlet` Missing

**What happened:**
The service crashed on startup with `ValueError: the greenlet library is required to use this function. No module named 'greenlet'`.

**Root cause:**
SQLAlchemy's async engine requires the `greenlet` library to bridge synchronous and asynchronous execution contexts internally. It is not automatically installed as a dependency of SQLAlchemy itself — it must be explicitly declared.

**Fix:**
Added `greenlet` to `requirements.txt` and installed it with `pip install greenlet`.

**Lesson:**
When using SQLAlchemy with async support, always include `greenlet` explicitly. This is a common gotcha that catches many developers the first time they use SQLAlchemy async.

---

## Environment Setup

### Prerequisites
- Homebrew Python 3.12
- Docker Desktop with PostgreSQL container running
- `inventory_db` database created (via `docker/postgres/init-multiple-dbs.sh`)

### Running Locally

```bash
cd inventory-service
/opt/homebrew/bin/python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8003 --loop asyncio
```

### Environment Variables (`.env`)

```
APP_NAME=inventory-service
APP_PORT=8003
POSTGRES_USER=admin
POSTGRES_PASSWORD=password
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=inventory_db
```

> **Note:** PostgreSQL port is `5433` (mapped from container's `5432`) due to a local PostgreSQL installation occupying the default port.

---

## Relationship with Other Services

```
Order Service
    │
    │ GET /api/inventory/{product_id}/check?quantity=N
    ▼
Inventory Service
    │
    │ PATCH /api/inventory/{product_id}/reduce
    ▼
PostgreSQL (inventory_db)
```

The Order Service calls Inventory Service **synchronously** before confirming any order. If inventory is insufficient, the order is rejected before it is saved to the database.

---

## Key Lessons Learned

**SQLAlchemy async requires explicit `greenlet` dependency.** Always add it to `requirements.txt` when using `sqlalchemy.ext.asyncio`.

**`available_qty` should be computed, not stored.** A computed property on the model guarantees consistency without synchronization overhead.

**PostgreSQL port mapping must match `.env`.** The container runs on `5432` internally but is mapped to `5433` on the host. The `.env` file must use the host port (`5433`) when connecting from outside Docker.

**Table creation at startup is fine for development.** `Base.metadata.create_all()` in the lifespan function is simple and reliable for local dev. Production deployments should use Alembic migrations instead.
