# 🏗️ Polyglot Microservices — E-Commerce Platform with AI

![CI](https://github.com/MicroServices-Project-Org/Python-Microservices/actions/workflows/ci.yml/badge.svg)

A production-grade microservices architecture built with **FastAPI**, **Spring Boot**, **Kafka**, **PostgreSQL**, **MongoDB**, **Elasticsearch**, **Redis**, and **Groq/Llama 3.3** — designed to demonstrate real-world patterns including event-driven communication, inter-service REST calls, JWT authentication, rate limiting, resilience patterns, full-text search, AI integration, full-stack observability with metrics + logs + distributed tracing, and a CI pipeline that runs all 210+ tests on every PR.

**Polyglot architecture:** Python services for core e-commerce + AI, Java service for search — demonstrating that microservices allow each service to use the best language for the job.

---

## 📐 System Architecture

```
                        ┌─────────────────┐
                        │   Angular/React  │
                        │    Frontend      │
                        └────────┬────────┘
                                 │ HTTPS
                        ┌────────▼────────┐
                        │   API Gateway   │  ← Rate limiting, JWT validation
                        │   (FastAPI)     │
                        │   Port: 9000    │
                        └──┬──┬──┬──┬──┬─┘
                           │  │  │  │  │
       ┌───────────────────┘  │  │  │  └──────────────────┐
       │             ┌────────┘  │  └────────┐             │
       ▼             ▼           ▼           ▼             ▼
┌────────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌───────────┐
│  Product   │ │  Order   │ │Inventory │ │   AI   │ │  Search   │
│  Service   │ │  Service │ │ Service  │ │Service │ │  Service  │
│ Python     │ │ Python   │ │ Python   │ │Python  │ │  Java     │
│ Port: 8001 │ │Port: 8002│ │Port: 8003│ │Pt: 8005│ │ Port: 8006│
└─────┬──────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ └─────┬─────┘
      │              │            │            │            │
   MongoDB      PostgreSQL   PostgreSQL   Groq/Llama  Elasticsearch
                     │
                ┌────▼──────────────────────┐
                │          KAFKA            │
                │  order-placed             │
                │  order-cancelled          │
                │  product-updated          │
                └────┬──────────┬───────────┘
                     │          │
          ┌──────────┤          ├───────────┐
          ▼          ▼          ▼           ▼
  ┌─────────────┐ ┌────────┐ ┌───────────┐
  │Notification │ │   AI   │ │  Search   │
  │  Service    │ │Service │ │  Service  │
  │ Port: 8004  │ │(Kafka  │ │(reindexes │
  │             │ │Consumer│ │on product │
  │  Redis      │ │+ LLM)  │ │ changes)  │
  └─────────────┘ └───┬────┘ └───────────┘
          ▲            │
          └────────────┘
          AI sends personalized
          content to Notification

  ┌─────────────────────────────────────────────────┐
  │              Keycloak (Port: 8081)              │
  │         OAuth2 / JWT Identity Provider          │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │           Observability Stack                   │
  │  Metrics:  Services → /metrics → Prometheus → Grafana │
  │  Logs:     Services → JSON files → Promtail → Loki    │
  │  Traces:   Services → OTLP → Tempo (correlated via    │
  │            trace_id in every log line)                │
  └─────────────────────────────────────────────────┘
```

---

## 🧩 Services Overview

| Service | Responsibility | Database | Port | Language | Status |
|---|---|---|---|---|---|
| **API Gateway** | Routing, JWT auth, rate limiting | None | 9000 | Python | ✅ Complete |
| **Product Service** | CRUD for product catalog, Kafka producer | MongoDB | 8001 | Python | ✅ Complete |
| **Order Service** | Place & manage orders, Kafka producer | PostgreSQL + Outbox | 8002 | Python | ✅ Complete |
| **Inventory Service** | Stock management, stock verification | PostgreSQL | 8003 | Python | ✅ Complete |
| **Notification Service** | Email notifications via Kafka events | Redis (idempotency) | 8004 | Python | ✅ Complete |
| **AI Service** | Recommendations, chatbot, smart search | None (stateless) | 8005 | Python | ✅ Complete |
| **Search Service** | Full-text search, autocomplete, filters, diff-and-reconcile | Elasticsearch | 8006 | Java | ✅ Complete |

All 7 services expose Prometheus metrics, emit JSON logs to Loki, and (Python services) export OpenTelemetry traces to Tempo.

---

## 🛠️ Tech Stack

| Category | Technology |
|---|---|
| **Python Framework** | FastAPI (async-native) |
| **Java Framework** | Spring Boot 3.3 + Java 21 |
| **Language** | Python 3.12, Java 21 |
| **Databases** | PostgreSQL 16, MongoDB 7.0 |
| **Search Engine** | Elasticsearch 8.13 |
| **Cache / Idempotency** | Redis 7.2 |
| **Message Broker** | Apache Kafka (Confluent 7.6.0) |
| **ORM** | SQLAlchemy (async) for PostgreSQL, Motor (async) for MongoDB, Spring Data JPA, Spring Data Elasticsearch |
| **Validation** | Pydantic v2, Jakarta Bean Validation |
| **HTTP Client** | httpx (async), RestTemplate (Spring) |
| **AI/LLM** | Groq (Llama 3.3 70B) — provider-agnostic, supports Gemini & Ollama |
| **Authentication** | Keycloak 24.0 (OAuth2 / JWT) + PyJWT |
| **Rate Limiting** | slowapi |
| **Resilience** | tenacity (retry), custom async circuit breaker, Spring `@Scheduled` (diff-and-reconcile) |
| **Observability** | Prometheus 2.51, Grafana 10.4, Loki 2.9, Tempo 2.4, Promtail, Micrometer, prometheus-fastapi-instrumentator, OpenTelemetry (FastAPI + httpx + logging + aiokafka instrumentation) |
| **CI/CD** | GitHub Actions (matrix-based parallel testing, pip + Maven caching, ruff lint) |
| **Containerization** | Docker, Docker Compose |
| **Testing** | pytest, pytest-asyncio, unittest.mock, JUnit 5, Mockito |

---

## 📦 Project Structure

```
Python-Microservices/
│
├── .github/
│   └── workflows/
│       └── ci.yml                        # GitHub Actions CI pipeline
│
├── api-gateway/                          # Python — FastAPI
│   ├── app/
│   │   ├── main.py                       # Proxy routes, /metrics, tracing
│   │   ├── config.py
│   │   ├── logging_config.py             # JSON logs with trace_id/span_id
│   │   ├── tracing_config.py             # OpenTelemetry setup → Tempo
│   │   ├── auth/keycloak.py              # JWT validation via JWKS
│   │   └── middleware/rate_limit.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── product-service/                      # Python — FastAPI + MongoDB + Kafka
│   ├── app/
│   │   ├── main.py
│   │   ├── logging_config.py
│   │   ├── tracing_config.py
│   │   ├── database.py                   # Motor async MongoDB
│   │   ├── schemas/product.py
│   │   ├── routes/product_routes.py
│   │   ├── services/product_service.py   # Publishes product-updated events
│   │   └── kafka/producer.py             # aiokafka producer
│   ├── tests/unit/test_product_service.py    # 22 tests
│   └── requirements.txt
│
├── order-service/                        # Python — FastAPI + PostgreSQL + Kafka
│   ├── app/
│   │   ├── main.py
│   │   ├── logging_config.py
│   │   ├── tracing_config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── order.py
│   │   │   └── outbox.py                 # Outbox table
│   │   ├── routes/order_routes.py
│   │   ├── services/
│   │   │   ├── order_service.py
│   │   │   └── outbox_worker.py          # Background worker: outbox → Kafka
│   │   ├── clients/inventory_client.py
│   │   └── kafka/producer.py
│   └── tests/                            # 52 tests
│
├── inventory-service/                    # Python — FastAPI + PostgreSQL
│   ├── app/
│   │   ├── main.py
│   │   ├── logging_config.py
│   │   ├── tracing_config.py
│   │   ├── models/inventory.py
│   │   ├── routes/inventory_routes.py
│   │   └── services/inventory_service.py
│   └── tests/                            # 18 tests
│
├── notification-service/                 # Python — FastAPI + Kafka + Redis
│   ├── app/
│   │   ├── main.py
│   │   ├── logging_config.py
│   │   ├── tracing_config.py
│   │   ├── kafka/consumer.py
│   │   └── services/email_service.py
│   └── tests/                            # 42 tests
│
├── ai-service/                           # Python — FastAPI + Kafka + LLM + Redis cache
│   ├── app/
│   │   ├── main.py
│   │   ├── logging_config.py
│   │   ├── tracing_config.py
│   │   ├── llm/                          # Provider-agnostic clients
│   │   ├── clients/product_client.py
│   │   ├── cache/redis_cache.py          # Cache-aside Redis layer (DB 1)
│   │   ├── routes/ai_routes.py
│   │   ├── services/
│   │   └── kafka/
│   └── tests/                            # 45 tests
│
├── search-service/                       # Java — Spring Boot + Elasticsearch
│   ├── src/main/java/com/ecommerce/search/
│   │   ├── SearchApplication.java        # @EnableScheduling
│   │   ├── config/
│   │   ├── controller/
│   │   ├── model/
│   │   ├── repository/
│   │   ├── service/
│   │   ├── kafka/ProductEventConsumer.java
│   │   └── scheduler/DiffReconcileJob.java
│   ├── src/main/resources/application.yml    # Actuator + Prometheus + histogram
│   ├── src/test/java/com/ecommerce/search/
│   │   ├── service/SearchServiceTest.java        # 15 tests
│   │   └── scheduler/DiffReconcileJobTest.java   # 10 tests
│   └── pom.xml
│
├── docker/
│   ├── prometheus/prometheus.yml             # Scrape configs for all 7 services
│   ├── grafana/provisioning/
│   │   ├── datasources/datasources.yml       # Prometheus, Loki, Tempo (pinned UIDs)
│   │   └── dashboards/
│   │       ├── dashboards.yml
│   │       └── microservices-overview.json   # 5 panels: metrics + logs
│   ├── loki/loki-config.yaml                 # Loki 2.9 with WAL fix
│   ├── promtail/promtail-config.yaml         # Tails Docker + service log files
│   └── tempo/tempo-config.yaml
│
├── logs/                                     # Gitignored — service JSON logs
├── docker-compose.yml
└── README.md
```

---

## 🔗 Inter-Service Communication

### Synchronous (REST/HTTP)
```
API Gateway     → All Services (proxy)
Order Service   → Inventory Service (stock check + reduce)
AI Service      → Product Service (fetch catalog for LLM context)
Search Service  → Product Service (diff-and-reconcile job, every 30 min)
```

### Asynchronous (Kafka)
```
Order Service   ──► [order-placed]          ──► Notification Service
Order Service   ──► [order-placed]          ──► AI Service
AI Service      ──► [ai-notification-ready] ──► Notification Service
Order Service   ──► [order-cancelled]       ──► Notification Service
Inventory Svc   ──► [inventory-low]         ──► Notification Service
Product Svc     ──► [product-updated]       ──► Search Service
```

### Outbox Pattern (Order Service)
```
BEGIN TRANSACTION
  1. Save order to PostgreSQL
  2. Save event to outbox table
COMMIT

Background worker:
  3. Read PENDING events → publish to Kafka → mark SENT
  4. Cleanup after 7 days
```

### Kafka Topics

| Topic | Producer | Consumers | Purpose |
|---|---|---|---|
| `order-placed` | Order Service | Notification, AI Service | New order |
| `order-cancelled` | Order Service | Notification Service | Cancellation |
| `inventory-low` | Inventory Service | Notification Service | Stock alert |
| `ai-notification-ready` | AI Service | Notification Service | Personalized email |
| `product-updated` | Product Service | Search Service | Reindex in Elasticsearch |

### `product-updated` Event Schema

```json
{
  "event_type": "PRODUCT_CREATED" | "PRODUCT_UPDATED" | "PRODUCT_DELETED",
  "timestamp": "2026-06-06T16:55:28Z",
  "product_id": "6a2451001d0dedd8bfa83d69",
  "product": {
    "id": "6a2451001d0dedd8bfa83d69",
    "name": "Bose QC45",
    "price": 279.99,
    "category": "Electronics",
    "tags": ["audio", "bose"],
    "stock_quantity": 15
  }
}
```

For `PRODUCT_DELETED` events, `product` is `null` and only `product_id` matters.

---

## 🗄️ Database Schemas

### Product Service — MongoDB
```json
Collection: products
{
  "_id": "ObjectId",
  "name": "iPhone 15 Pro",
  "price": 999.99,
  "category": "Electronics",
  "tags": ["smartphone", "apple", "5g"],
  "stock_quantity": 100,
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

### Order Service — PostgreSQL
```
Table: orders
  id (UUID, PK) | order_number | customer_name | customer_email
  total_amount   | status (ENUM) | created_at   | updated_at
  Status: PENDING → CONFIRMED → SHIPPED → DELIVERED → CANCELLED

Table: order_items
  id (UUID, PK) | order_id (FK) | product_id | product_name
  quantity       | unit_price    | total_price

Table: outbox
  id (UUID, PK) | topic | event_payload (JSON) | status (PENDING/SENT)
  created_at     | sent_at
```

### Inventory Service — PostgreSQL
```
Table: inventory
  id (UUID, PK)  | product_id (unique) | product_name
  quantity        | reserved_qty        | created_at | updated_at
  Computed: available_qty = quantity - reserved_qty
```

### Search Service — Elasticsearch
```json
Index: products
{
  "name": "iPhone 15 Pro",
  "price": 999.99,
  "category": "Electronics",
  "tags": ["smartphone", "apple", "5g"],
  "suggest": { "input": ["iPhone", "iPhone 15", "iPhone 15 Pro"] }
}
```

---

## 🔌 API Endpoints

> **All requests go through the API Gateway on port 9000.**

### API Gateway (Port 9000)
| Method | Path | Proxies To | Rate Limit |
|---|---|---|---|
| `*` | `/api/products/**` | Product Service :8001 | 60/min |
| `*` | `/api/orders/**` | Order Service :8002 | 60/min |
| `*` | `/api/inventory/**` | Inventory Service :8003 | 60/min |
| `*` | `/api/ai/**` | AI Service :8005 | 15/min |
| `*` | `/api/search/**` | Search Service :8006 | 60/min |

### Product Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/products` | Create product (publishes `PRODUCT_CREATED`) |
| `GET` | `/api/products` | List products |
| `GET` | `/api/products/search?q=` | Search by name/category/tags |
| `GET` | `/api/products/{id}` | Get by ID |
| `PUT` | `/api/products/{id}` | Update (publishes `PRODUCT_UPDATED`) |
| `DELETE` | `/api/products/{id}` | Delete (publishes `PRODUCT_DELETED`) |

### Order Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/orders` | Place a new order |
| `GET` | `/api/orders` | List all orders |
| `GET` | `/api/orders/{order_id}` | Get by ID |
| `GET` | `/api/orders/user/{email}` | Orders by customer |
| `PATCH` | `/api/orders/{order_id}/status` | Update status |
| `PATCH` | `/api/orders/{order_id}/cancel` | Cancel |

### Inventory Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/inventory` | Add inventory item |
| `GET` | `/api/inventory` | List all |
| `GET` | `/api/inventory/{product_id}` | Stock for product |
| `GET` | `/api/inventory/{product_id}/check?quantity=N` | Check availability |
| `PATCH` | `/api/inventory/{product_id}/reduce` | Reduce stock |
| `PATCH` | `/api/inventory/{product_id}/restock` | Restock |

### AI Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/chat` | Shopping chatbot |
| `GET` | `/api/ai/recommendations` | Product recommendations |
| `POST` | `/api/ai/suggest` | Natural language product search |

### Search Service (Java)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/search?q=` | Full-text + fuzzy via `multi_match` + `AUTO` |
| `GET` | `/api/search/autocomplete?q=` | Type-ahead suggestions |
| `GET` | `/api/search/filter?category=&minPrice=&maxPrice=` | Faceted filtering |

### Observability Endpoints (all services)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/metrics` (Python) | Prometheus-format metrics |
| `GET` | `/actuator/prometheus` (Search Service) | Spring Actuator metrics |

---

## 🔄 End-to-End Order Flow

```
1.  Client → POST :9000/api/orders (via API Gateway)
2.  Gateway validates JWT → proxies to Order Service
3.  Order Service → GET /api/inventory/{id}/check (verify stock)
4.  If in stock → save order to PostgreSQL
5.  Save event to outbox table (same transaction — guaranteed)
6.  Order Service → PATCH /api/inventory/{id}/reduce
7.  Background worker reads outbox → publishes 'order-placed' to Kafka
8.  Notification Service → consumes → checks Redis (idempotency) → email
9.  AI Service → consumes → generates personalized email via LLM
10. AI Service → publishes 'ai-notification-ready' to Kafka
11. Notification Service → consumes AI event → personalized email
12. Return 201 Created to client
```

Every step is **traced end-to-end** in Tempo — one trace_id stitches together all spans from API Gateway through Order, Inventory, and back, with each log line tagged by the same trace_id.

---

## 🤖 AI Features

| Feature | Endpoint | LLM Provider | Description |
|---|---|---|---|
| Shopping Chatbot | `POST /api/ai/chat` | Groq (Llama 3.3 70B) | Conversational assistant |
| Recommendations | `GET /api/ai/recommendations` | Groq | 5 related products |
| Smart Search | `POST /api/ai/suggest` | Groq | Natural language → products |
| Email Personalization | Kafka event | Groq | AI-generated emails |

### Provider-Agnostic Design
Switch by changing one line in `.env`:
```
LLM_PROVIDER=groq      # Groq / Llama 3.3 70B (current)
LLM_PROVIDER=gemini    # Google Gemini
LLM_PROVIDER=ollama    # Ollama (local)
```

### Redis Caching (Cache-Aside)
AI Service caches LLM-returned product IDs (6h TTL) and catalog data (15min TTL) in Redis DB 1. Live product details fetched fresh. Chat responses not cached (conversation history makes full-response caching unsafe).

---

## 🔍 Search Features (Java Spring Boot)

| Feature | Endpoint | Description |
|---|---|---|
| Full-text search | `GET /api/search?q=` | `multi_match` with `AUTO` fuzziness, `name^3` boost |
| Autocomplete | `GET /api/search/autocomplete?q=` | Prefix suggestions |
| Faceted filters | `GET /api/search/filter?...` | Category, price range |

### How Search Stays in Sync

**MongoDB is the source of truth.** Elasticsearch is a derived, read-optimized index. Data flows one way: MongoDB → Elasticsearch. The Search Service never writes back to MongoDB.

**Layer 1 — Event-driven via Kafka (happy path)**
```
Product Service → Kafka: product-updated → Search Service → Elasticsearch
```
Fire-and-forget; Kafka failures never block product writes.

**Layer 2 — Diff-and-reconcile job (safety net, every 30 min)**
```
Search Service reads both stores → computes diff → writes only to Elasticsearch
```
The scheduled job:
1. Reads all products from MongoDB (paginated through Product Service API)
2. Reads all document IDs from Elasticsearch
3. Computes the diff and issues writes only to Elasticsearch (upserts from Mongo, deletes orphans)
4. MongoDB is never modified by this job

**Why diff-and-reconcile over outbox?** Outbox guarantees Kafka write durability but doesn't handle ES corruption, missed events while Search was offline, or schema drift. Diff-and-reconcile catches all three because it's a full convergent sync.

---

## 📊 Observability

The project ships with a complete observability stack: **metrics, logs, and distributed traces — all correlated**. This is the same three-pillar model used at scale in production.

### Stack at a glance

| Concern | Tool | Where to look |
|---|---|---|
| Metrics | Prometheus + Grafana | http://localhost:3000 → Microservices Overview dashboard |
| Logs | Loki + Promtail | Grafana → Explore → Loki, or the dashboard's Service Logs panel |
| Traces | Tempo + OpenTelemetry | Grafana → Explore → Tempo |
| Correlation | `trace_id` in every log line | Click trace_id in Loki → jumps to Tempo |

### 1. Metrics

Every service exposes Prometheus-format metrics. Prometheus scrapes them every 15 seconds.

- **Python services** use `prometheus-fastapi-instrumentator==7.0.0` exposing `/metrics` with request counts, status codes, and latency histograms.
- **Search Service (Java)** uses Spring Boot Actuator + Micrometer at `/actuator/prometheus`, with histogram buckets enabled for `http.server.requests` at SLO targets (50ms/100ms/200ms/500ms/1s/2s).

**Grafana dashboard — "Microservices Overview":**
| Panel | Description |
|---|---|
| Request Rate | req/s per service (Python + Spring queries unified) |
| Error Rate (5xx) | Per-service percentage with `clamp_min` to prevent divide-by-zero blowup |
| p95 Latency | 95th percentile latency per service via `histogram_quantile()` |
| Service Status | UP/DOWN per service from `up{}` |
| Service Logs | Live JSON-parsed log entries (Loki) |

**Networking note:** Services run on the host, not in Docker, so Prometheus scrapes them via `host.docker.internal:<port>`.

### 2. Logs

Every Python service emits **structured JSON logs** to both stdout and a file under `./logs/` (gitignored). Promtail tails the files and ships them to Loki. Each line includes:

```json
{
  "timestamp": "2026-06-07 01:11:42,261",
  "level": "INFO",
  "logger": "app.routes.order_routes",
  "message": "Order ORD-... created",
  "service": "order-service",
  "trace_id": "ad2e1f41703def52b97f785204369023",
  "span_id": "d25c39cca59d6195"
}
```

Loki indexes by `service` and `level` labels (set in Promtail's pipeline_stages). Grafana queries like `{service="order-service", level="ERROR"}` work out of the box.

### 3. Distributed Traces

Every Python service is instrumented with **OpenTelemetry** auto-instrumentation:
- `FastAPIInstrumentor` — server spans for every incoming HTTP request
- `HTTPXClientInstrumentor` — propagates trace context on outgoing HTTP calls
- `AIOKafkaInstrumentor` — Kafka producer/consumer spans (where applicable)

Spans are exported via OTLP gRPC to Tempo on `localhost:4317`. The `service.name` resource attribute tags each span.

**One trace, multiple services:** A single `POST /api/orders` request produces ~18 spans across 3 services (api-gateway → order-service → inventory-service), visible as a single waterfall in Grafana → Explore → Tempo.

**Log ↔ Trace correlation:** A custom logging filter pulls the current span's `trace_id` and `span_id` from the OpenTelemetry context on every log call. Click a `trace_id` in a Loki log → jump to the same trace in Tempo. Click a span in Tempo → jump to its logs in Loki (configured via `tracesToLogsV2` in datasource provisioning).

### Quick verification commands

```bash
# Metrics
open http://localhost:9090/targets         # All 7 should be UP
open http://localhost:3000                 # admin/admin → Microservices Overview

# Logs (after generating traffic)
curl http://localhost:9000/api/products
# Then in Grafana Explore (Loki): {service=~".+"}

# Traces
curl -X POST http://localhost:9000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Test","customer_email":"t@t.com","items":[{"product_id":"prod-001","product_name":"X","quantity":1,"unit_price":10}]}'
# Then in Grafana Explore (Tempo): Search → Service: api-gateway → run → click latest trace
```

---

## 🔐 Security

```
1. User logs in via Keycloak → gets JWT access token
2. Client sends JWT: Authorization: Bearer <token>
3. API Gateway validates JWT with Keycloak public keys (RS256)
4. If valid → strips auth header, forwards to downstream service
5. Services trust requests from Gateway (internal network)
```

> **Note:** `AUTH_ENABLED=false` by default for development. Set to `true` when Keycloak is configured.

---

## 🛡️ Resilience Patterns

| Pattern | Library | Applied At | Fallback |
|---|---|---|---|
| **Outbox Pattern** | PostgreSQL | Order Service → Kafka | Events survive Kafka outages |
| **Idempotency** | Redis `SET NX` | Notification Service | Prevents duplicate emails |
| **Diff-and-Reconcile Job** | Spring `@Scheduled` | Search Service → Elasticsearch | Self-heals from Kafka/ES drift |
| **Circuit Breaker** | Custom async (~80 LOC) | Order → Inventory | Returns "service unavailable" |
| **Retry + Backoff** | tenacity | Order → Inventory, AI → LLM | Raise after max retries |
| **Timeout** | httpx | All inter-service calls | Raise timeout exception |
| **Rate Limiter** | slowapi | API Gateway | 429 Too Many Requests |
| **Cache-Aside** | Redis | AI Service | Graceful fallback on Redis failure |
| **Fire-and-Forget Kafka** | aiokafka | Product Service producer | Reconcile job catches missed events |

---

## 🧪 Testing

| Service | Language | Tests | Covers |
|---|---|---|---|
| API Gateway | Python | 31 | Routing, proxying, JWT |
| Product Service | Python | 22 | CRUD, search, Kafka publishing |
| Order Service | Python | 52 | Order creation, stock checks, cancellation, outbox, circuit breaker |
| Inventory Service | Python | 18 | CRUD, stock check, reduce, restock |
| Notification Service | Python | 42 | Email templates, SMTP, Kafka routing |
| AI Service | Python | 45 | All 3 LLM providers, 4 AI features |
| Search Service | Java | 25 | Search, fuzzy match, autocomplete, diff-and-reconcile |

**Total: 235+ unit tests**

```bash
# Python
cd <service> && source venv/bin/activate && pytest -v

# Java
cd search-service && mvn test
```

---

## ⚙️ CI/CD

Every PR and every push to `main` triggers a GitHub Actions workflow that runs the full test suite. The workflow is defined in `.github/workflows/ci.yml`.

### Pipeline structure

```
On PR / push to main:
  ├── Python tests (matrix, parallel)
  │     ├── api-gateway       → pytest
  │     ├── product-service   → pytest
  │     ├── order-service     → pytest
  │     ├── inventory-service → pytest
  │     ├── notification-service → pytest
  │     └── ai-service        → pytest
  ├── Java tests
  │     └── search-service    → mvn test
  └── Lint
        └── ruff check (non-blocking)
```

### What each job does

| Job | Tool | Caching | Notes |
|---|---|---|---|
| Python tests (×6) | pytest | pip cache per service | Matrix runs in parallel, `fail-fast: false` so all failures surface |
| Java tests | Maven | Maven repo cache | First run ~5 min, cached runs ~30s |
| Lint | ruff | — | `continue-on-error: true` — runs but doesn't block PRs initially |

### Why this design

- **Matrix strategy** = 6 Python services in parallel. End-to-end pipeline runs in ~3-5 min instead of ~15 min serially.
- **`fail-fast: false`** = if one service breaks, the others still run. Surfacing all failures is more useful than stopping at the first.
- **Caching** = subsequent runs are dramatically faster. pip and Maven both hash the lockfile/pom to invalidate appropriately.
- **No integration tests in CI** = unit tests fully mock external dependencies (Kafka, Postgres, MongoDB, Redis). CI focuses on logic correctness, not deployment health. Integration testing happens locally via Docker Compose.
- **Lint non-blocking** = ruff finds lots of style nits on a project this size. We'll tighten over time without blocking ongoing work.

### Status check

The CI workflow appears as a status check on every PR. Branch protection on `main` requires all required checks to pass before merging.

---

## 🐳 Infrastructure (Docker Compose)

| Service | Port | Purpose |
|---|---|---|
| MongoDB | 27017 | Product Service |
| PostgreSQL | 5433 | Order + Inventory |
| Elasticsearch | 9200 | Search Service |
| Redis | 6379 | Notification + AI cache |
| Kafka | 9092 | Event streaming |
| Zookeeper | 2181 | Kafka coordination |
| Kafka UI | 8090 | Visual Kafka management |
| Keycloak | 8081 | OAuth2 / JWT |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Dashboards (admin/admin) |
| Loki | 3100 | Log aggregation |
| Promtail | 9080 | Log shipper |
| Tempo | 3200 (HTTP), 4317 (OTLP gRPC), 4318 (OTLP HTTP) | Distributed tracing |

```bash
docker-compose up -d
docker ps --format "table {{.Names}}\t{{.Status}}"
```

---

## 🚀 Running the Application

### Prerequisites
- macOS with Homebrew
- Python 3.12 (via Homebrew, **not** Anaconda)
- Java 21 (for Search Service)
- Docker Desktop
- Groq API key (free at https://console.groq.com/keys)

### Step 1 — Start Infrastructure
```bash
cd Python-Microservices
docker-compose up -d
```

### Step 2 — Start Services (each in a separate terminal)

```bash
# Terminal 1: Product Service
cd product-service && source venv/bin/activate
python -m uvicorn app.main:app --port 8001 --loop asyncio

# Terminal 2: Inventory Service
cd inventory-service && source venv/bin/activate
python -m uvicorn app.main:app --port 8003 --loop asyncio

# Terminal 3: Order Service
cd order-service && source venv/bin/activate
python -m uvicorn app.main:app --port 8002 --loop asyncio

# Terminal 4: Notification Service
cd notification-service && source venv/bin/activate
python -m uvicorn app.main:app --port 8004 --loop asyncio

# Terminal 5: AI Service
cd ai-service && source venv/bin/activate
python -m uvicorn app.main:app --port 8005 --loop asyncio

# Terminal 6: Search Service (Java)
cd search-service
mvn spring-boot:run

# Terminal 7: API Gateway
cd api-gateway && source venv/bin/activate
python -m uvicorn app.main:app --port 9000 --loop asyncio
```

Each Python service logs two init lines on startup:
```
"Logging initialized for <service>"
"Tracing initialized for <service> → http://localhost:4317"
```

### Step 3 — Generate traffic
```bash
# Health
curl http://localhost:9000/health

# Add inventory + place order (full Kafka flow + distributed trace)
curl -X POST http://localhost:9000/api/inventory \
  -H "Content-Type: application/json" \
  -d '{"product_id":"prod-001","product_name":"iPhone 15 Pro","quantity":100}'

curl -X POST http://localhost:9000/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name":"Yash Vyas",
    "customer_email":"yash@example.com",
    "items":[{"product_id":"prod-001","product_name":"iPhone 15 Pro","quantity":1,"unit_price":999.99}]
  }'

# AI
curl -X POST http://localhost:9000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What products do you have?"}'

# Search (fuzzy)
curl "http://localhost:9000/api/search?q=iphne"
curl "http://localhost:9000/api/search/autocomplete?q=iph"
```

### Step 4 — Observe

- **Metrics**: http://localhost:3000 (admin/admin) → Microservices Overview
- **Logs**: same dashboard, scroll to Service Logs panel — or Grafana Explore → Loki → `{service=~".+"}`
- **Traces**: Grafana Explore → Tempo → Search → service `api-gateway` → run → click latest order trace

A `POST /api/orders` produces ~18 spans across api-gateway, order-service, and inventory-service, all linked by one `trace_id` that also appears in every log line for that request.

---

## 📝 Service Documentation

| Service | Documentation |
|---|---|
| Product Service | [`product-service/product-service-docs.md`](product-service/product-service-docs.md) |
| Order Service | [`order-service/order-docs.md`](order-service/order-docs.md) |
| Inventory Service | [`inventory-service/inventory-docs.md`](inventory-service/inventory-docs.md) |
| Notification Service | [`notification-service/notification-docs.md`](notification-service/notification-docs.md) |
| AI Service | [`ai-service/ai-service-docs.md`](ai-service/ai-service-docs.md) |
| API Gateway | [`api-gateway/api-gateway-docs.md`](api-gateway/api-gateway-docs.md) |
| Search Service | [`search-service/search-service-docs.md`](search-service/search-service-docs.md) |

---

## 🐛 Notable Issues & Fixes

| Issue | Root Cause | Fix |
|---|---|---|
| Anaconda interfering with async event loop | venv inherited Anaconda's sys.path | Removed Anaconda, used Homebrew Python |
| MongoDB auth failing from host to Docker | SCRAM auth broken over Docker TCP bridge on Mac | Disabled auth for local dev |
| `motor` + `pymongo` version incompatibility | Motor relied on removed PyMongo internals | Pinned compatible versions |
| PostgreSQL init script not running | Data volume already initialized | `docker-compose down -v` to reset |
| Port conflicts on Mac (8080, 5432) | Local processes occupying ports | Remapped to 8081, 5433 |
| SQLAlchemy async missing `greenlet` | Not auto-installed | Added to requirements.txt |
| Gemini daily rate limit exhausted | Kafka burst + retry cascading | Switched to Groq, added throttling |
| `pybreaker` broken on Python 3.12 | Tornado dependency issue | Custom 80-line async circuit breaker |
| Lombok failing on Java 21 + Maven | Annotation processing | Removed Lombok, explicit getters/setters |
| Local Homebrew Redis conflicting with Docker Redis | Port 6379 collision | `brew services stop redis` |
| Spring Data ES `Criteria.matches()` not fuzzy | API doesn't expose fuzziness | Switched to `StringQuery` with `multi_match` + `AUTO` |
| Mockito failing on Java 25 Byte Buddy | Byte Buddy supports up to Java 23 | Pinned project to Java 21 |
| Search Service consumer indexed empty products | Consumer read fields from event root; producer publishes them nested under `product` | Consumer unwraps `product` field; also handles `PRODUCT_DELETED` |
| `prometheus-fastapi-instrumentator==8.0.0` broke FastAPI | v8 pulls in starlette 1.x; FastAPI 0.129 requires <1.0 | Pinned to `7.0.0` |
| Prometheus targets all DOWN | Used Docker container names but services run on host | Switched scrape targets to `host.docker.internal:<port>` |
| Grafana panels showed "No data" | Dashboard referenced datasource UID "prometheus" but auto-generated UID differed | Pinned `uid:` for all datasources in provisioning |
| Error Rate panel showed 10000% with no traffic | Tiny divisor (~0) inflated ratio | `clamp_min(divisor, 0.001)` in PromQL |
| Search Service missing from p95 Latency | Spring `http.server.requests` exports count/sum but not histogram buckets by default | Enabled `percentiles-histogram` + SLO buckets in `application.yml` |
| Loki crash-loop: `permission denied at /wal` | Loki 2.9 wants WAL at root, no permission | Configured `ingester.wal.dir: /loki/wal` |
| Promtail Docker scrape error: client version 1.42 too old | Docker API requires 1.44+ now | Ignored for service-log path; will upgrade Promtail in future PR |
| `LoggingInstrumentor` didn't inject trace_id into JSON logs | Field names didn't line up with formatter expectations | Custom `ContextFilter` that pulls `trace_id`/`span_id` from `opentelemetry.trace.get_current_span()` directly |
| Inventory Service crashed: `No module named 'httpx'` | OTel httpx instrumentation imports httpx even if service doesn't use it | `pip install httpx` in inventory-service venv |
| CI failed: `No module named 'bson'` | requirements.txt missing transitive deps (motor→pymongo→bson) | Regenerated all 6 services' requirements.txt via `pip freeze` |
| Order Service tests broke after outbox refactor | Tests patched `publish_order_placed` which no longer exists | Replaced with assertion that an Outbox row was added |
| inventory-service tests had `ModuleNotFoundError: No module named 'app'` | pytest.ini missing `pythonpath = .` | Added to pytest.ini |

---

## 🗺️ Build Roadmap

```
Phase 1 ✅ Infrastructure
  └── Docker Compose (Kafka, PostgreSQL, MongoDB, Keycloak, Observability)

Phase 2 ✅ Core Services
  ├── Product Service (Python, MongoDB, Motor async)
  ├── Inventory Service (Python, PostgreSQL, SQLAlchemy async)
  └── Order Service (Python, PostgreSQL, httpx, aiokafka)

Phase 3 ✅ Async Layer
  └── Notification Service (Python, Kafka consumer, Gmail SMTP)

Phase 4 ✅ AI Layer
  └── AI Service (Python, Groq/Llama 3.3 70B, provider-agnostic, Kafka, Redis caching)

Phase 5 ✅ Gateway & Security
  └── API Gateway (Python, routing, JWT via Keycloak, rate limiting)

Phase 6 ✅ Resilience & Reliability
  ├── Outbox Pattern in Order Service (PostgreSQL — guaranteed Kafka delivery)
  ├── Idempotency in Notification Service (Redis SET NX)
  ├── Custom async Circuit Breaker on Order → Inventory
  ├── Retry + Backoff on Order → Inventory, AI → LLM (tenacity)
  └── Timeouts on all HTTP calls (httpx)

Phase 7 ✅ Search Service (Java Spring Boot)
  ├── Spring Boot 3.3 + Java 21
  ├── Elasticsearch full-text search (multi_match + AUTO fuzziness + name^3 boost)
  ├── Autocomplete + faceted filtering
  └── 15 unit tests

Phase 7.5 ✅ Product → Search Event Sync
  ├── aiokafka producer in Product Service
  ├── Search Service consumer fix (nested product field, PRODUCT_DELETED handling)
  ├── DiffReconcileJob (Mongo-authoritative, 30 min interval)
  └── 15 new tests

Phase 8.1 ✅ Observability — Metrics
  ├── Prometheus scrapes all 7 services
  ├── Python: prometheus-fastapi-instrumentator
  ├── Spring: Actuator + Micrometer with histogram buckets
  ├── Grafana provisioned datasources (pinned UIDs)
  └── Microservices Overview dashboard (4 metric panels)

Phase 8.2 ✅ Observability — Logs
  ├── Loki crash-loop fix (WAL config)
  ├── Promtail file-tailing for host-run services
  ├── JSON structured logging in all 6 Python services
  ├── trace_id / span_id injected into every log line (via OTel API)
  └── Service Logs panel added to dashboard

Phase 8.3 ✅ Observability — Distributed Tracing
  ├── OpenTelemetry on all 6 Python services
  ├── Auto-instrumentation: FastAPI, httpx, logging, aiokafka
  ├── OTLP gRPC export to Tempo
  ├── HTTP context propagation across services
  ├── Verified end-to-end trace: api-gateway → order → inventory (~18 spans)
  └── Log↔Trace correlation via custom ContextFilter

Phase 9 ✅ CI/CD
  ├── GitHub Actions workflow on every PR + push to main
  ├── Matrix strategy: 6 Python services tested in parallel
  ├── Java Search Service tested with mvn test
  ├── pip and Maven caching for fast re-runs
  ├── Ruff lint job (non-blocking initially)
  └── Branch protection on main requires all checks to pass

Future / nice-to-have:
  - Containerize services (currently run on host for dev iteration speed)
  - Kafka span propagation (notification + AI consumer spans join the request trace)
  - OpenTelemetry on Search Service (Java)
  - Docker image builds in CI → push to ghcr.io
  - Alertmanager + Slack/email routing on metric thresholds
```

---

## 💼 Resume-Worthy Highlights

- **Polyglot microservices** — Python (FastAPI) + Java (Spring Boot) showing language-per-service architecture
- **Outbox pattern** for guaranteed Kafka delivery in Order Service (transactional outbox + background worker)
- **Hybrid sync pattern** for Product → Search: Kafka events for low-latency + diff-and-reconcile job for convergent correctness, with MongoDB as strict source of truth (chosen over outbox because reconcile also handles ES corruption and schema drift)
- **Cache-aside Redis caching** in AI Service with 6h TTL for LLM responses, graceful fallback on Redis failure
- **Idempotency via Redis SET NX** in Notification Service prevents duplicate emails
- **Custom async circuit breaker** (~80 LOC) when pybreaker proved incompatible with Python 3.12
- **Provider-agnostic LLM layer** supporting Groq, Gemini, and Ollama with a one-line config switch
- **Full-stack observability** — Prometheus metrics, JSON-structured logs in Loki, OpenTelemetry distributed traces in Tempo. One `trace_id` stitches together ~18 spans across 3 services for a single order request, and the same `trace_id` appears in every log line, enabling one-click pivot from log to trace in Grafana
- **CI/CD with GitHub Actions** — every PR runs the full test suite (235+ tests) across all 7 services in parallel via matrix strategy; pip and Maven caching keep runs under 5 minutes; branch protection on main requires green checks before merge
- **235+ unit tests** across 7 services using pytest, JUnit 5, and Mockito

---

## 📄 License

Built for learning and portfolio purposes.

---

## 👤 Author

**Yash Vyas**