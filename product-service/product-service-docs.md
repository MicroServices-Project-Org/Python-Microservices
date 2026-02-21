# Product Service — Technical Documentation

## Overview

The Product Service is the first microservice built in the FastAPI Microservices project. It manages the product catalog using a REST API backed by MongoDB. This document covers architecture decisions, issues encountered during development, and how they were resolved.

---

## Tech Stack Decisions

### FastAPI over Flask or Django
FastAPI was chosen because it is async-native, which is essential for a microservices architecture where services make many concurrent I/O calls. It also provides automatic OpenAPI/Swagger documentation out of the box, and Pydantic v2 integration for request/response validation. Flask is synchronous by default and Django carries too much overhead for a single-responsibility microservice.

### MongoDB over PostgreSQL
The product catalog is a good fit for MongoDB because product schemas are flexible — different product categories may have different attributes. MongoDB's document model handles this naturally without requiring schema migrations every time a new product type is added. In contrast, the Order and Inventory services use PostgreSQL because they deal with transactional, relational data where strict schemas and ACID compliance matter.

### Motor over PyMongo
Motor is the async driver for MongoDB, built on top of PyMongo. Since FastAPI runs on an async event loop, using synchronous PyMongo directly would block the event loop and kill performance. Motor wraps PyMongo operations to run asynchronously, keeping the event loop free during database I/O.

### Pydantic v2 for Validation
Pydantic v2 handles all input validation automatically. If a client sends `price: -50`, it is rejected before the code even runs. This eliminates an entire class of bugs and removes the need to write manual validation logic.

### Homebrew Python over Anaconda
Anaconda was removed from the project environment because it caused critical interference with the async event loop. When Anaconda's base environment was active, its thread executor (`/opt/anaconda3/lib/python3.12/concurrent/futures/thread.py`) was being used instead of the venv's, causing Motor to fall back to synchronous PyMongo. This resulted in authentication failures that were misleading and difficult to trace. Homebrew Python provides a clean, isolated runtime without this interference.

---

## Project Structure

```
product-service/
├── app/
│   ├── main.py                  # FastAPI app entrypoint and lifespan
│   ├── config.py                # Settings loaded from .env via pydantic-settings
│   ├── database.py              # Motor async MongoDB client
│   ├── models/                  # Empty — not needed for MongoDB (see below)
│   ├── schemas/
│   │   └── product.py           # Pydantic request/response models
│   ├── routes/
│   │   └── product_routes.py    # API endpoint definitions
│   └── services/
│       └── product_service.py   # Business logic and DB operations
├── tests/
│   └── unit/
│       └── test_product_service.py
├── Dockerfile
└── requirements.txt
```

### Why No Models Folder?
In Java/Spring Boot, you need separate `@Entity` classes for JPA and DTO classes for request/response. In Python with MongoDB, Motor works directly with Python dictionaries — there is no ORM layer required. Pydantic schemas handle both validation and serialization. The `models/` folder exists but is intentionally empty for this service. The Order and Inventory services will use SQLAlchemy ORM models since they use PostgreSQL.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/products` | Create a new product |
| `GET` | `/api/products` | List all products (paginated) |
| `GET` | `/api/products/search?q=` | Search by name, category, or tags |
| `GET` | `/api/products/{id}` | Get product by ID |
| `PUT` | `/api/products/{id}` | Update product fields |
| `DELETE` | `/api/products/{id}` | Delete a product |
| `GET` | `/health` | Health check |

---

## Issues Encountered and Fixes

### Issue 1 — Anaconda Interfering with Async Event Loop

**What happened:**
Every write operation to MongoDB returned a 500 Internal Server Error with `Authentication failed`. The error traceback consistently showed `/opt/anaconda3/lib/python3.12/concurrent/futures/thread.py` — Anaconda's thread executor — even though a virtual environment was activated. Motor was falling back to synchronous PyMongo instead of using async operations.

**Root cause:**
The virtual environment was originally created using Anaconda's Python interpreter. Even after activating the venv, Anaconda's libraries leaked into the runtime because the venv inherited Anaconda's sys.path. This caused Motor's async coroutines to be dispatched through Anaconda's thread executor, which broke the SCRAM authentication handshake.

**Fix:**
Removed Anaconda's initialization block from `~/.zshrc`, created a new venv using Homebrew Python (`/opt/homebrew/bin/python3.12 -m venv venv`), and reinstalled all dependencies cleanly. The prompt changed from `(venv) (base)` to `(venv)` confirming Anaconda was fully removed.

---

### Issue 2 — MongoDB Authentication Failing from Outside Docker

**What happened:**
Even with the correct credentials, PyMongo consistently failed to authenticate when connecting from the Mac host to MongoDB running in Docker. The same credentials worked perfectly inside the Docker container via `mongosh`.

**Root cause:**
Two separate issues combined:
1. PyMongo defaulted to `SCRAM-SHA-1` for the initial authentication handshake but could not discover the supported mechanisms because the `saslSupportedMechs` query requires sending the username during the `hello` command — which was not happening correctly over the Docker TCP bridge on Mac.
2. The MongoDB container was running version `6.0.22` instead of `7.0.30` due to Docker image caching, causing version-specific auth behavior differences.

**Fix:**
Removed MongoDB authentication entirely for local development by removing the `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD` environment variables from `docker-compose.yml`. This is the standard industry practice for local development environments — MongoDB only accepts connections from localhost, so there is no security risk. Authentication will be properly configured in the containerized deployment in Phase 7 where all services communicate over Docker's internal network.

---

### Issue 3 — motor and pymongo Version Incompatibility

**What happened:**
`motor==3.4.0` with `pymongo==4.16.0` (the latest at the time) threw `ImportError: cannot import name '_QUERY_OPTIONS' from 'pymongo.cursor'`.

**Root cause:**
Motor 3.4.0 was built against an older PyMongo API. PyMongo 4.16.0 removed internal symbols that Motor relied on.

**Fix:**
Downgraded to a known compatible combination: `motor==3.5.1` with `pymongo==4.8.0`. Motor and PyMongo must always be upgraded together and tested as a pair.

---

### Issue 4 — Pydantic `decimal_places` Constraint Error

**What happened:**
The service failed to start with `ValueError: Unknown constraint decimal_places` when using `Decimal` fields with `Field(gt=0, decimal_places=2)` in Pydantic v2.

**Root cause:**
Pydantic v2 changed how `Decimal` constraints work. The `decimal_places` argument is not directly supported on `Optional[Decimal]` fields in the same way as v1.

**Fix:**
Replaced `Decimal` fields with `float` throughout the schemas. For a portfolio project this is acceptable. In a production financial system, `Decimal` with proper constraints would be required to avoid floating point precision issues.

---

### Issue 5 — OpenTelemetry `pkg_resources` Import Error

**What happened:**
The service crashed on startup with `ModuleNotFoundError: No module named 'pkg_resources'` when importing `opentelemetry-instrumentation-fastapi`.

**Root cause:**
`pkg_resources` is provided by `setuptools` but newer Python versions and certain virtual environment configurations do not include it by default. The OpenTelemetry instrumentation library used the legacy `pkg_resources` import instead of the modern `importlib.metadata`.

**Fix:**
Removed all OpenTelemetry dependencies from the Product Service for now. Observability wiring (Prometheus metrics, Tempo tracing) will be added as a dedicated phase (Phase 8) once all services are built, using a properly tested configuration.

---

### Issue 6 — Docker Compose `version` Attribute Warning

**What happened:**
Every `docker-compose` command printed: `the attribute 'version' is obsolete, it will be ignored`.

**Root cause:**
Docker Compose v2 deprecated the top-level `version` field in `docker-compose.yml`.

**Fix:**
Removed the `version: "3.8"` line from `docker-compose.yml`.

---

### Issue 7 — PostgreSQL Init Script Not Running

**What happened:**
After starting the stack, `order_db` and `inventory_db` databases were missing from PostgreSQL. Only the default databases existed.

**Root cause:**
The `init-multiple-dbs.sh` script mounted at `/docker-entrypoint-initdb.d/` only runs when the data directory is completely empty. Previous `docker-compose up` runs had already initialized the volume, so the script was skipped on subsequent runs.

**Fix:**
Used `docker-compose down -v` to remove all volumes, then ran `docker-compose up -d` again. The `-v` flag removes named volumes, forcing PostgreSQL to reinitialize and run the init script. Also ensured the script had executable permissions via `chmod +x docker/postgres/init-multiple-dbs.sh`.

---

### Issue 8 — Port Conflicts on Mac

**What happened:**
Docker failed to start with `ports are not available: exposing port TCP 0.0.0.0:8080` and later `0.0.0.0:5432`.

**Root cause:**
Port 8080 was occupied by a Java process (likely a leftover Spring Boot application). Port 5432 was occupied by a local PostgreSQL installation.

**Fix:**
Remapped the conflicting ports in `docker-compose.yml`:
- Keycloak: `8080:8080` → `8081:8080`
- PostgreSQL: `5432:5432` → `5433:5432`

The internal container ports remain unchanged — only the host-side mapping changes. Services inside Docker still communicate using the original ports.

---

## Environment Setup

### Prerequisites
- Homebrew Python 3.12 (not Anaconda)
- Docker Desktop
- Virtual environment per service

### Running Locally

```bash
# Start infrastructure
cd Python-Microservices
docker-compose up -d

# Run product service
cd product-service
/opt/homebrew/bin/python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8001 --loop asyncio
```

### Environment Variables (`.env`)

```
APP_NAME=product-service
APP_PORT=8001
MONGO_HOST=127.0.0.1
MONGO_PORT=27017
DB_NAME=product_db
```

> **Note:** MongoDB authentication is disabled for local development. The `.env` file is in `.gitignore` and must never be committed.

---

## Key Lessons Learned

**Virtual environments must be created with the correct Python interpreter.** A venv created from Anaconda inherits Anaconda's libraries. Always use `which python` after activation to confirm the interpreter path.

**MongoDB authentication behaves differently over Docker's TCP bridge on Mac.** Auth that works inside the container may fail from the host. For local development, disabling auth is the pragmatic solution.

**Motor and PyMongo must be upgraded together.** They are tightly coupled. Never upgrade one without checking compatibility with the other.

**Local development does not need production-level security.** MongoDB auth, HTTPS, and JWT validation are important in production but add unnecessary friction during local development. They belong in the containerized deployment phase.

**CI/CD catches issues early.** The `hadolint` linter in GitHub Actions caught an unpinned `pip install` in the Dockerfile that would have been a silent issue in production builds.
