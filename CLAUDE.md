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

`docker compose up -d` starts **infrastructure only** (Mongo, Postgres on host port **5433**, Kafka on 9092, Redis, Elasticsearch, Keycloak on 8081, Prometheus, Grafana, Loki, Tempo, Promtail). The 7 app services are in the compose profile **`apps`**, so there are two ways to run them:

```bash
# A: everything in Docker
docker compose --profile apps up -d --build
docker compose up -d --build order-service      # rebuild one after a code change
docker compose --profile apps down

# B: services on the host (one terminal each), infrastructure in Docker
docker compose up -d
cd <service> && source venv/bin/activate
python -m uvicorn app.main:app --port <port> --loop asyncio
cd search-service && mvn spring-boot:run
```

A third mode is Kubernetes on kind: `./k8s/deploy.sh` (see `k8s/README.md`; gateway via Traefik on `localhost:8080`, no Keycloak or observability yet). It needs about as much memory as Compose, so stop one before starting the other. In k8s, hostnames come from the `app-config` ConfigMap and secrets from `k8s/secrets.env` (gitignored), and **every Pod needs `enableServiceLinks: false`**, or injected `REDIS_PORT=tcp://...` variables break `Settings` and the Kafka image.

Both Compose modes publish the same host ports, so run a given service one way at a time. In Docker, a service loads its `<service>/.env` (`env_file`, optional) for secrets and flags, but `docker-compose.yml` overrides every host-specific value in `environment:` (Kafka `kafka:29092`, Postgres `postgres:5432`, `mongodb`, `redis`, `tempo:4317`, `http://<service>:<port>` URLs), and Postgres/Mongo credentials come from the root `.env`. **If you add a setting that points at `localhost`, add its container override there too.** The gateway checks tokens against `KEYCLOAK_URL=http://localhost:8081` (the issuer clients see) but fetches signing keys from `KEYCLOAK_INTERNAL_URL=http://keycloak:8080`. Containers bind-mount `./logs` at `/logs` (`LOG_DIR`), so Promtail ships the same files in both modes, and Prometheus scrapes `host.docker.internal:<port>` (`docker/prometheus/prometheus.yml`), which reaches either mode. Images are multi-stage and non-root, and search builds its jar inside the image. CI (`docker-validate.yml`) builds all 7 images from a clean checkout.

**Config:** each Python service reads its own `<service>/.env` (gitignored), and the root `.env` is read only by `docker-compose.yml`. Each has a committed `.env.example` with every key, using default values or `your-*` placeholders for secrets. `Settings` forbids unknown keys, so a stale key in `.env` crashes startup. **If you add, rename, or remove a `Settings` field, update that service's `.env.example` too.** `tests/unit/test_env_example.py` fails CI if they drift.

Defaults in each `config.py` point at `localhost`. Useful flags:
- `api-gateway`: `AUTH_ENABLED=false` by default (JWT checks are skipped).
- `notification-service`: `EMAIL_ENABLED=false` by default (no real SMTP).
- `ai-service`: `LLM_PROVIDER` defaults to `groq` (other options are `gemini` and `ollama`), with `GROQ_MODEL=openai/gpt-oss-120b`. Groq retires models: a 404 `model_not_found` means you should pick one from `GET https://api.groq.com/openai/v1/models`. `app/llm/factory.py` creates the client at import time, so an unknown provider fails on startup.

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
- Tests ignore your local `.env`. Each service's `tests/conftest.py` replaces `app.config.settings` with `Settings(_env_file=None)` before any test module is imported, so tests see the `config.py` defaults, the same as CI. Shell env vars still override (`AUTH_ENABLED=true pytest`). The same conftest also points `LOG_DIR` at a temp dir, so tests never write to `logs/<service>.log` (Promtail would ship them to Loki). Keep `app/config.py` free of `app.*` imports, or the swap can happen too late.
- All tests are unit tests. They need no running infrastructure because DB sessions, Kafka, httpx, Redis, and LLM clients are mocked with `unittest.mock` (`AsyncMock`/`MagicMock`/`patch`). Gateway tests use `httpx.ASGITransport` against `app.main.app` and patch `app.main.http_client`. Follow these patterns and do not add tests that need live services.
- `scripts/test-keycloak-flow.sh` is an end-to-end auth check. It needs `docker-compose up -d` plus the gateway running with `AUTH_ENABLED=true`, and exits non-zero on failure. Note that the gateway disables JWT audience verification (`verify_aud: False` in `api-gateway/app/auth/keycloak.py`).
- CI (`.github/workflows/ci.yml`) runs a matrix of `pip install -r requirements.txt && pytest -v` for each Python service, `mvn test` for search, and `ruff check .` (non-blocking). `docker-validate.yml` checks compose/config files, runs hadolint on Dockerfiles, and requires `docker/postgres/init-multiple-dbs.sh` to stay executable.
- `requirements.txt` files are frozen from working venvs. Pins matter: `prometheus-fastapi-instrumentator==7.0.0` (v8 breaks FastAPI via starlette 1.x). The Motor/PyMongo versions are also pinned together.

## Cross-cutting conventions

- **`logging_config.py` and `tracing_config.py` are identical copies in all six Python services.** If you change one, change all six. `setup_logging(name)` runs at import time in `main.py`, and `setup_tracing(name, app)` runs after the app is created. Logs are JSON (stdout + `logs/<service>.log`) with `trace_id`/`span_id` injected by a custom `ContextFilter`. The file handler rotates at `LOG_MAX_BYTES` (10 MB) with `LOG_BACKUP_COUNT` (3) backups. These are shell env vars like `LOG_DIR`, not `Settings` fields, so don't put them in `.env`. Rotation assumes one process per log file: a second writer (e.g. a second copy of the service without its own `LOG_DIR`) keeps writing to the renamed `.log.1`, which Promtail doesn't tail. Loki keeps 7 days (compactor retention in `docker/loki/loki-config.yaml`). `RepeatThrottleFilter` lets each repeated aiokafka WARNING/ERROR through once per 60s (the next one carries `suppressed_repeats`), because during a Kafka outage aiokafka logs every ~100ms retry. Traces go via OTLP gRPC to Tempo at `OTLP_ENDPOINT` (default `localhost:4317`).
- Every Python service exposes `/health` and `/metrics` (Instrumentator). Search exposes `/actuator/prometheus`.
- A lot of existing code logs with `print()` and emoji. Newer code uses `logging`. `print` output does not reach Loki, so use `logging` in new code.
- Outbound HTTP uses `httpx.AsyncClient` with explicit `httpx.Timeout`.

## Key flows and where they live

- **Gateway proxy** (`api-gateway/app/main.py`): each backend has explicit `/api/<svc>` and `/api/<svc>/{path:path}` routes with `@limiter.limit(...)` and `Depends(verify_token)`. AI routes use the stricter `RATE_LIMIT_AI`. To add a new downstream service, add both routes and a `*_SERVICE_URL` setting. `SERVICE_MAP` is not used for routing.
- **Order placement** (`order-service/app/services/order_service.py`): check stock via `clients/inventory_client.py`, save the order and its items, reduce stock over HTTP, then add an `Outbox` row. The order, items, and outbox row go in one DB transaction, which `get_db()` in `database.py` commits after the handler returns. The HTTP stock reduction is outside that transaction. Events are never published to Kafka directly from request handlers. `services/outbox_worker.py` polls `PENDING` rows every 5s, publishes them, marks them `SENT`, and deletes them after 7 days.
- **Order → Inventory resilience** (`order-service/app/clients/`): tenacity retry (3 attempts, exponential backoff) wraps a custom async `CircuitBreaker` (`circuit_breaker.py`; `pybreaker` breaks on 3.12). `HTTPException` is excluded so that 4xx responses do not trip the breaker.
- **Kafka outages**: nothing should die or block startup when Kafka is down. Consumers (notification, AI order-placed, AI cache invalidator, inventory restock) run in a retry loop (`RETRY_SECONDS = 10`). product-service starts without Kafka and retries the producer in the background (events are skipped meanwhile, and Search's reconcile job repairs them). order-service's outbox worker calls `ensure_producer()` each poll, so PENDING events are delivered once Kafka is back. Keep new Kafka clients to the same pattern.
- **Restock on cancel** (`inventory-service/app/kafka/consumer.py`): inventory consumes `order-cancelled` and adds each item's quantity back. It is idempotent via a `processed_events` row written in the same transaction as the stock `UPDATE`, and it commits offsets manually after that transaction, so a DB error retries the event instead of dropping it.
- **Kafka topics**: `order-placed`, `order-cancelled` (order), `ai-notification-ready` (ai → notification), and `product-updated` (product → search, AI cache). There are no low-stock alerts (an unused `inventory-low` consumer was removed in #39). Topics are auto-created. The `product-updated` payload nests fields under `product`, which is `null` on `PRODUCT_DELETED`. The Java consumer (`kafka/ProductEventConsumer.java`) depends on that shape.
- **Notification idempotency** (`notification-service/app/kafka/consumer.py`): Redis `SET NX` with a 7-day TTL for each event, applied before sending.
- **AI service**: providers implement `LLMClient.generate()` (`app/llm/base.py`) and are registered in `factory.py`. It calls Product Service over HTTP for catalog context (`get_all_products()` pages through the whole catalog). `/recommendations` and `/suggest` never return raw LLM text: `app/services/llm_output.py` parses the JSON, keeps only products whose names match the catalog, and takes id/price from the catalog. An unparseable reply returns 502. Redis cache (DB 1) in `app/cache/redis_cache.py`: the catalog (15 min) and the validated LLM picks (ids + reasons, 6 h), with details always filled in from the current catalog. Keys are versioned (`ai:v<N>:...`), and `kafka/cache_invalidator.py` bumps the version on every `product-updated` event. Every Redis call fails soft. Tests never hit real Redis, because an autouse fixture in `tests/conftest.py` disables the cache (use a fake, like `test_redis_cache.py` does).
- **Search sync**: MongoDB is the source of truth. Search is kept current by the Kafka consumer plus a scheduled reconcile job (`scheduler/DiffReconcileJob.java`, configured by `reconciliation.*`) that pages through the Product Service API and writes only to Elasticsearch. Search traces through Micrometer Tracing (OTel bridge) over **OTLP HTTP on 4318**, not gRPC 4317 like the Python services, and logs JSON via `logback-spring.xml` (same fields, `${LOG_DIR}/search-service.log`, default `../logs`). Build HTTP clients from the injected `RestTemplateBuilder`, or calls won't propagate the trace. Do not rely on Lombok in the search service. Getters and setters are written by hand because Lombok broke on Java 21.

## Gotchas

- Postgres runs on host port **5433**, not 5432. A single container hosts both `order_db` and `inventory_db`, created by `docker/postgres/init-multiple-dbs.sh`.
- **A Homebrew `mongod` may shadow Docker's MongoDB.** If `brew services` runs `mongodb-community` on `localhost:27017`, host-mode product-service connects to it (no auth) instead of the `mongodb` container. That is where the old "SCRAM auth fails over the Docker bridge" belief came from. In Docker mode, product-service uses the `mongodb` container with the root user (`MONGO_USERNAME`/`MONGO_PASSWORD`, empty = no auth). The two databases hold separate catalogs, and Search's reconcile job syncs Elasticsearch to whichever product-service is running. Check with `lsof -iTCP:27017 -sTCP:LISTEN`.
- Every stateful container has a named volume, so `docker compose down` keeps data and `down -v` wipes it all. Kafka (`kafka_data`) and Zookeeper (`zookeeper_data`, `zookeeper_log`) must be removed together, or Kafka fails with `InconsistentClusterIdException`. Redis runs with `--appendonly yes` so notification's idempotency keys survive restarts.
- Tables are created by `Base.metadata.create_all` in `lifespan`. There are no migrations, so a schema change on an existing table needs a manual `ALTER` or a dropped volume.
- Use Homebrew Python 3.12, not Anaconda (it breaks the asyncio loop). Search needs Java 21 exactly, because Mockito/Byte Buddy fails on newer JDKs.
- Per-service doc filenames aren't uniform (`ai-service/ai-docs.md`, `api-gateway/gw-docs.md`). Use the README's "Service Documentation" table as the index, and update it if you add or rename a doc. Notification has no doc yet.
- `KNOWN_ISSUES.md` lists open bugs, code/doc mismatches, and the infra roadmap. When you fix an issue, replace its write-up with a row in the Fixed table (with the PR number), and don't renumber the rest.
