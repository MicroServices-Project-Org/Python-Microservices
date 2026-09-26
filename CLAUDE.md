# CLAUDE.md

Polyglot e-commerce microservices: six Python/FastAPI services plus one Java/Spring Boot search service, connected over REST and Kafka. `README.md` has the full architecture, endpoint tables, event schemas, and a list of past issues and their fixes. `system-design.md` has the design rationale. This file covers what you need to work in the code.

## Layout

Every service is a self-contained project with its own dependencies, `venv/`, `.env`, and tests. There is no shared Python package and no root-level Python tooling.

| Dir | Port | Stack | Backing store |
|---|---|---|---|
| `api-gateway/` | 9000 | FastAPI, slowapi, PyJWT (Keycloak JWKS) | — |
| `product-service/` | 8001 | FastAPI, Motor | MongoDB `product_db` |
| `order-service/` | 8002 | FastAPI, SQLAlchemy async/asyncpg | Postgres `order_db` |
| `inventory-service/` | 8003 | FastAPI, SQLAlchemy async/asyncpg | Postgres `inventory_db` |
| `notification-service/` | 8004 | FastAPI, aiokafka consumer, SMTP | Redis (idempotency) |
| `ai-service/` | 8005 | FastAPI, aiokafka, Groq/Gemini/Ollama | — |
| `search-service/` | 8006 | Spring Boot 3.3, Java 21, Maven | Elasticsearch |

Python services use the same layout: `app/main.py` (FastAPI app + `lifespan`), `app/config.py` (pydantic-settings `Settings`, reads `.env`), and `app/{routes,services,schemas,models,clients,kafka}/`. Routes stay thin, and business logic lives in `app/services/*.py` as module-level async functions.

## Running

**`docker-compose.yml` starts infrastructure only** (Mongo, Postgres on host port **5433**, Kafka on 9092, Redis, Elasticsearch, Keycloak on 8081, Prometheus, Grafana, Loki, Tempo, Promtail). The application services run on the host. Their Dockerfiles exist but compose does not use them.

```bash
docker-compose up -d

# each Python service, in its own terminal
cd <service> && source venv/bin/activate
python -m uvicorn app.main:app --port <port> --loop asyncio

cd search-service && mvn spring-boot:run
```

Because the services run on the host, Prometheus scrapes them at `host.docker.internal:<port>` (`docker/prometheus/prometheus.yml`), and Promtail tails the JSON log files in `./logs/`. Keep both in mind if you containerize a service.

**Config:** each Python service reads its own `<service>/.env` (gitignored), and the root `.env` is read only by `docker-compose.yml`. Each has a committed `.env.example` with every key, using default values or `your-*` placeholders for secrets. `Settings` forbids unknown keys, so a stale key in `.env` crashes startup. **If you add, rename, or remove a `Settings` field, update that service's `.env.example` too.** `tests/unit/test_env_example.py` fails CI if they drift.

Defaults in each `config.py` point at `localhost`. Useful flags:
- `api-gateway`: `AUTH_ENABLED=false` by default (JWT checks are skipped).
- `notification-service`: `EMAIL_ENABLED=false` by default (no real SMTP).
- `ai-service`: `LLM_PROVIDER` defaults to `groq` (other options are `gemini` and `ollama`). `app/llm/factory.py` creates the client at import time, so an unknown provider fails on startup.

## Testing

```bash
# Python: run from inside the service directory
cd <service> && source venv/bin/activate && pytest -v
pytest tests/unit/test_order_service.py::test_name -v   # single test

# Java
cd search-service && mvn test
mvn test -Dtest=DiffReconcileJobTest
```

- `pytest.ini` in each service sets `asyncio_mode = auto` and `testpaths = tests`. Tests must be run with the service directory as the working directory so that `app.` imports resolve.
- Tests ignore your local `.env`. Each service's `tests/conftest.py` replaces `app.config.settings` with `Settings(_env_file=None)` before any test module is imported, so tests see the `config.py` defaults, the same as CI. Shell env vars still override (`AUTH_ENABLED=true pytest`). Keep `app/config.py` free of `app.*` imports, or the swap can happen too late.
- All tests are unit tests. They need no running infrastructure because DB sessions, Kafka, httpx, Redis, and LLM clients are mocked with `unittest.mock` (`AsyncMock`/`MagicMock`/`patch`). Gateway tests use `httpx.ASGITransport` against `app.main.app` and patch `app.main.http_client`. Follow these patterns and do not add tests that need live services.
- `scripts/test-keycloak-flow.sh` is an end-to-end auth check. It needs `docker-compose up -d` plus the gateway running with `AUTH_ENABLED=true`, and exits non-zero on failure. Note that the gateway disables JWT audience verification (`verify_aud: False` in `api-gateway/app/auth/keycloak.py`).
- CI (`.github/workflows/ci.yml`) runs a matrix of `pip install -r requirements.txt && pytest -v` for each Python service, `mvn test` for search, and `ruff check .` (non-blocking). `docker-validate.yml` checks compose/config files, runs hadolint on Dockerfiles, and requires `docker/postgres/init-multiple-dbs.sh` to stay executable.
- `requirements.txt` files are frozen from working venvs. Pins matter: `prometheus-fastapi-instrumentator==7.0.0` (v8 breaks FastAPI via starlette 1.x). The Motor/PyMongo versions are also pinned together.

## Cross-cutting conventions

- **`logging_config.py` and `tracing_config.py` are identical copies in all six Python services.** If you change one, change all six. `setup_logging(name)` runs at import time in `main.py`, and `setup_tracing(name, app)` runs after the app is created. Logs are JSON (stdout + `logs/<service>.log`) with `trace_id`/`span_id` injected by a custom `ContextFilter`. Traces go via OTLP gRPC to Tempo at `OTLP_ENDPOINT` (default `localhost:4317`).
- Every Python service exposes `/health` and `/metrics` (Instrumentator). Search exposes `/actuator/prometheus`.
- A lot of existing code logs with `print()` and emoji. Newer code uses `logging`. `print` output does not reach Loki, so use `logging` in new code.
- Outbound HTTP uses `httpx.AsyncClient` with explicit `httpx.Timeout`.

## Key flows and where they live

- **Gateway proxy** (`api-gateway/app/main.py`): each backend has explicit `/api/<svc>` and `/api/<svc>/{path:path}` routes with `@limiter.limit(...)` and `Depends(verify_token)`. AI routes use the stricter `RATE_LIMIT_AI`. To add a new downstream service, add both routes and a `*_SERVICE_URL` setting. `SERVICE_MAP` is not used for routing.
- **Order placement** (`order-service/app/services/order_service.py`): check stock via `clients/inventory_client.py`, save the order and its items, reduce stock over HTTP, then add an `Outbox` row. The order, items, and outbox row go in one DB transaction, which `get_db()` in `database.py` commits after the handler returns. The HTTP stock reduction is outside that transaction. Events are never published to Kafka directly from request handlers. `services/outbox_worker.py` polls `PENDING` rows every 5s, publishes them, marks them `SENT`, and deletes them after 7 days.
- **Order → Inventory resilience** (`order-service/app/clients/`): tenacity retry (3 attempts, exponential backoff) wraps a custom async `CircuitBreaker` (`circuit_breaker.py`; `pybreaker` breaks on 3.12). `HTTPException` is excluded so that 4xx responses do not trip the breaker.
- **Kafka topics**: `order-placed`, `order-cancelled` (order), `inventory-low`, `ai-notification-ready` (ai), and `product-updated` (product → search). Topics are auto-created. The `product-updated` payload nests fields under `product`, which is `null` on `PRODUCT_DELETED`. The Java consumer (`kafka/ProductEventConsumer.java`) depends on that shape.
- **Notification idempotency** (`notification-service/app/kafka/consumer.py`): Redis `SET NX` with a 7-day TTL for each event, applied before sending.
- **AI service**: providers implement `LLMClient.generate()` (`app/llm/base.py`) and are registered in `factory.py`. It calls Product Service over HTTP for catalog context (`get_all_products()` pages through the whole catalog). `/recommendations` and `/suggest` never return raw LLM text: `app/services/llm_output.py` parses the JSON, keeps only products whose names match the catalog, and takes id/price from the catalog. An unparseable reply returns 502. The README describes a Redis cache at `app/cache/redis_cache.py`, but that module does not exist in the repo yet.
- **Search sync**: MongoDB is the source of truth. Search is kept current by the Kafka consumer plus a scheduled reconcile job (`scheduler/DiffReconcileJob.java`, configured by `reconciliation.*`) that pages through the Product Service API and writes only to Elasticsearch. Do not rely on Lombok in the search service. Getters and setters are written by hand because Lombok broke on Java 21.

## Gotchas

- Postgres runs on host port **5433**, not 5432. A single container hosts both `order_db` and `inventory_db`, created by `docker/postgres/init-multiple-dbs.sh`.
- MongoDB is reached without auth from the host (`product-service/app/database.py`) even though compose sets root credentials. This was done on purpose to work around SCRAM auth failing over the Docker bridge on macOS.
- Tables are created by `Base.metadata.create_all` in `lifespan`. There are no migrations, so a schema change on an existing table needs a manual `ALTER` or a dropped volume.
- Use Homebrew Python 3.12, not Anaconda (it breaks the asyncio loop). Search needs Java 21 exactly, because Mockito/Byte Buddy fails on newer JDKs.
- Per-service doc filenames aren't uniform (`ai-service/ai-docs.md`, `api-gateway/gw-docs.md`). Use the README's "Service Documentation" table as the index, and update it if you add or rename a doc. Notification has no doc yet.
- `KNOWN_ISSUES.md` lists open bugs, code/doc mismatches, and the infra roadmap. When you fix an issue, replace its write-up with a row in the Fixed table (with the PR number), and don't renumber the rest.
