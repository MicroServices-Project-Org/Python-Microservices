# 🏗️ FastAPI Microservices — E-Commerce Platform with AI

A production-grade microservices architecture built with **FastAPI**, **Kafka**, **PostgreSQL**, **MongoDB**, and **Groq/Llama 3.3** — designed to demonstrate real-world patterns including event-driven communication, inter-service REST calls, JWT authentication, rate limiting, resilience patterns, and AI integration.

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
                        └──┬──┬──┬──┬────┘
                           │  │  │  │
          ┌────────────────┘  │  │  └─────────────────┐
          │             ┌─────┘  └─────┐               │
          ▼             ▼              ▼                ▼
  ┌──────────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐
  │   Product    │ │  Order   │ │  Inventory   │ │    AI    │
  │   Service    │ │  Service │ │   Service    │ │  Service │
  │  Port: 8001  │ │Port: 8002│ │  Port: 8003  │ │Port: 8005│
  └──────┬───────┘ └────┬─────┘ └──────┬───────┘ └────┬─────┘
         │              │              │               │
    MongoDB         PostgreSQL    PostgreSQL     Groq / Llama 3.3
                         │
                    ┌────▼─────────────────────┐
                    │         KAFKA            │
                    │   Topic: order-placed    │
                    └────┬─────────────────────┘
                         │
              ┌──────────┴───────────┐
              ▼                      ▼
     ┌─────────────────┐    ┌─────────────────┐
     │  Notification   │    │   AI Service    │
     │    Service      │    │  (Kafka Consumer│
     │   Port: 8004    │    │  + personalizes │
     └─────────────────┘    │   the email)    │
              ▲             └────────┬────────┘
              └──────────────────────┘
               AI sends personalized
               content to Notification

  ┌─────────────────────────────────────────────────┐
  │              Keycloak (Port: 8081)              │
  │         OAuth2 / JWT Identity Provider          │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │           Observability Stack                   │
  │  Prometheus → Grafana │ Loki (logs) │ Tempo     │
  └─────────────────────────────────────────────────┘
```

---

## 🧩 Services Overview

| Service | Responsibility | Database | Port | Status |
|---|---|---|---|---|
| **API Gateway** | Routing, JWT auth, rate limiting | None | 9000 | ✅ Complete |
| **Product Service** | CRUD for product catalog | MongoDB | 8001 | ✅ Complete |
| **Order Service** | Place & manage orders, Kafka producer | PostgreSQL | 8002 | ✅ Complete |
| **Inventory Service** | Stock management, stock verification | PostgreSQL | 8003 | ✅ Complete |
| **Notification Service** | Email notifications via Kafka events | None (stateless) | 8004 | ✅ Complete |
| **AI Service** | Recommendations, chatbot, smart search | None (stateless) | 8005 | ✅ Complete |

---

## 🛠️ Tech Stack

| Category | Technology |
|---|---|
| **Framework** | FastAPI (async-native) |
| **Language** | Python 3.12 |
| **Databases** | PostgreSQL 16, MongoDB 7.0 |
| **Message Broker** | Apache Kafka (Confluent 7.6.0) |
| **ORM** | SQLAlchemy (async) for PostgreSQL, Motor (async) for MongoDB |
| **Validation** | Pydantic v2 |
| **HTTP Client** | httpx (async) |
| **AI/LLM** | Groq (Llama 3.3 70B) — provider-agnostic, supports Gemini & Ollama |
| **Authentication** | Keycloak 24.0 (OAuth2 / JWT) + PyJWT |
| **Rate Limiting** | slowapi |
| **Resilience** | tenacity (retry), pybreaker (circuit breaker) |
| **Observability** | Prometheus, Grafana, Loki, Tempo |
| **Containerization** | Docker, Docker Compose |
| **Testing** | pytest, pytest-asyncio, unittest.mock |

---

## 📦 Project Structure

```
Python-Microservices/
│
├── api-gateway/
│   ├── app/
│   │   ├── main.py                  # Proxy routes, shared httpx client
│   │   ├── config.py                # Service URLs, Keycloak, rate limits
│   │   ├── auth/
│   │   │   └── keycloak.py          # JWT validation via JWKS
│   │   └── middleware/
│   │       └── rate_limit.py        # slowapi rate limiter
│   ├── tests/
│   │   └── unit/
│   │       ├── test_gateway.py
│   │       └── test_auth.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── product-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py              # Motor async MongoDB client
│   │   ├── schemas/
│   │   │   └── product.py
│   │   ├── routes/
│   │   │   └── product_routes.py
│   │   └── services/
│   │       └── product_service.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── order-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py              # SQLAlchemy async + PostgreSQL
│   │   ├── models/
│   │   │   └── order.py             # Orders + order_items ORM
│   │   ├── schemas/
│   │   │   └── order.py
│   │   ├── routes/
│   │   │   └── order_routes.py
│   │   ├── services/
│   │   │   └── order_service.py
│   │   ├── clients/
│   │   │   └── inventory_client.py  # httpx client for Inventory Service
│   │   └── kafka/
│   │       └── producer.py          # aiokafka producer
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── inventory-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py              # SQLAlchemy async + PostgreSQL
│   │   ├── models/
│   │   │   └── inventory.py
│   │   ├── schemas/
│   │   │   └── inventory.py
│   │   ├── routes/
│   │   │   └── inventory_routes.py
│   │   └── services/
│   │       └── inventory_service.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── notification-service/
│   ├── app/
│   │   ├── main.py                  # FastAPI + Kafka consumer background task
│   │   ├── config.py
│   │   ├── kafka/
│   │   │   └── consumer.py          # aiokafka consumer for 4 topics
│   │   └── services/
│   │       └── email_service.py     # Gmail SMTP + HTML email templates
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── ai-service/
│   ├── app/
│   │   ├── main.py                  # FastAPI + Kafka consumer background task
│   │   ├── config.py
│   │   ├── llm/
│   │   │   ├── base.py              # Abstract LLMClient interface
│   │   │   ├── gemini_client.py     # Google Gemini
│   │   │   ├── groq_client.py       # Groq / Llama 3.3 70B
│   │   │   ├── ollama_client.py     # Ollama (local)
│   │   │   └── factory.py           # Provider factory
│   │   ├── clients/
│   │   │   └── product_client.py    # Fetches real catalog for LLM context
│   │   ├── routes/
│   │   │   └── ai_routes.py         # Chat, recommendations, suggest
│   │   ├── services/
│   │   │   ├── chatbot.py
│   │   │   ├── recommendation.py
│   │   │   ├── suggestion.py
│   │   │   └── notification_ai.py
│   │   └── kafka/
│   │       ├── consumer.py          # Consumes order-placed
│   │       └── producer.py          # Publishes ai-notification-ready
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker/
│   ├── postgres/
│   │   └── init-multiple-dbs.sh
│   ├── keycloak/
│   │   └── realm-export.json
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── grafana/
│   │   └── provisioning/
│   ├── loki/
│   │   └── loki-config.yaml
│   ├── promtail/
│   │   └── promtail-config.yaml
│   └── tempo/
│       └── tempo-config.yaml
│
├── docker-compose.yml
└── README.md
```

---

## 🔗 Inter-Service Communication

### Synchronous (REST/HTTP)
```
API Gateway    → All Services (proxy)
Order Service  → Inventory Service (stock check + reduce)
AI Service     → Product Service (fetch catalog for LLM context)
```

### Asynchronous (Kafka)
```
Order Service ──► [order-placed]          ──► Notification Service (confirmation email)
Order Service ──► [order-placed]          ──► AI Service (personalize email)
AI Service    ──► [ai-notification-ready] ──► Notification Service (personalized email)
Order Service ──► [order-cancelled]       ──► Notification Service (cancellation email)
Inventory Svc ──► [inventory-low]         ──► Notification Service (low stock alert)
```

### Kafka Topics

| Topic | Producer | Consumers | Purpose |
|---|---|---|---|
| `order-placed` | Order Service | Notification, AI Service | New order created |
| `order-cancelled` | Order Service | Notification Service | Order cancelled |
| `inventory-low` | Inventory Service | Notification Service | Stock alert |
| `ai-notification-ready` | AI Service | Notification Service | Personalized email ready |

---

## 🗄️ Database Schemas

### Product Service — MongoDB
```json
Collection: products
{
  "_id": "ObjectId",
  "name": "iPhone 15 Pro",
  "description": "Latest Apple smartphone",
  "price": 999.99,
  "category": "Electronics",
  "tags": ["smartphone", "apple", "5g"],
  "stock_quantity": 100,
  "image_url": "https://...",
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
```

### Inventory Service — PostgreSQL
```
Table: inventory
  id (UUID, PK)  | product_id (unique) | product_name
  quantity        | reserved_qty        | created_at | updated_at

  Computed: available_qty = quantity - reserved_qty
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

### Product Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/products` | Create a new product |
| `GET` | `/api/products` | List all products |
| `GET` | `/api/products/search?q=` | Search by name, category, or tags |
| `GET` | `/api/products/{id}` | Get product by ID |
| `PUT` | `/api/products/{id}` | Update product |
| `DELETE` | `/api/products/{id}` | Delete product |

### Order Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/orders` | Place a new order |
| `GET` | `/api/orders` | Get all orders |
| `GET` | `/api/orders/{order_id}` | Get order by ID |
| `GET` | `/api/orders/user/{email}` | Get orders by customer email |
| `PATCH` | `/api/orders/{order_id}/status` | Update order status |
| `PATCH` | `/api/orders/{order_id}/cancel` | Cancel an order |

### Inventory Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/inventory` | Add inventory item |
| `GET` | `/api/inventory` | List all inventory |
| `GET` | `/api/inventory/{product_id}` | Get stock for product |
| `GET` | `/api/inventory/{product_id}/check?quantity=N` | Check stock availability |
| `PATCH` | `/api/inventory/{product_id}/reduce` | Reduce stock |
| `PATCH` | `/api/inventory/{product_id}/restock` | Restock item |

### AI Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/chat` | Shopping assistant chatbot |
| `GET` | `/api/ai/recommendations` | Product recommendations |
| `POST` | `/api/ai/suggest` | Natural language product search |

### Notification Service
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check (no REST API — event-driven only) |

---

## 🔄 End-to-End Order Flow

```
1. Client → POST :9000/api/orders (via API Gateway)
2. Gateway validates JWT → proxies to Order Service
3. Order Service → GET /api/inventory/{id}/check (verify stock)
4. If in stock → save order to PostgreSQL
5. Order Service → PATCH /api/inventory/{id}/reduce (reduce stock)
6. Order Service → publish 'order-placed' to Kafka
7. Notification Service → consumes event → logs/sends confirmation email
8. AI Service → consumes event → generates personalized email via LLM
9. AI Service → publishes 'ai-notification-ready' to Kafka
10. Notification Service → consumes AI event → logs/sends personalized email
11. Return 201 Created to client
```

---

## 🤖 AI Features

| Feature | Endpoint | LLM Provider | Description |
|---|---|---|---|
| Shopping Chatbot | `POST /api/ai/chat` | Groq (Llama 3.3 70B) | Conversational assistant with real product context |
| Recommendations | `GET /api/ai/recommendations` | Groq (Llama 3.3 70B) | 5 related products from real catalog |
| Smart Search | `POST /api/ai/suggest` | Groq (Llama 3.3 70B) | Natural language → matching products |
| Email Personalization | Kafka event | Groq (Llama 3.3 70B) | AI-generated follow-up emails |

### Provider-Agnostic Design
The AI Service supports 3 LLM providers. Switch by changing one line in `.env`:
```
LLM_PROVIDER=groq      # Groq / Llama 3.3 70B (current)
LLM_PROVIDER=gemini    # Google Gemini
LLM_PROVIDER=ollama    # Ollama (local, no API key)
```

---

## 🔐 Security

```
1. User logs in via Keycloak → gets JWT access token
2. Client sends JWT: Authorization: Bearer <token>
3. API Gateway validates JWT with Keycloak public keys (RS256)
4. If valid → strips auth header, forwards to downstream service
5. If invalid → 401 Unauthorized
6. If expired → 403 Forbidden
7. Services trust all requests from Gateway (internal network)
```

> **Note:** `AUTH_ENABLED=false` by default for development. Set to `true` when Keycloak is configured.

---

## 🧪 Testing

Each service has unit tests using `pytest` with `unittest.mock` for mocking external dependencies.

| Service | Test Files | Tests | What's Covered |
|---|---|---|---|
| API Gateway | `test_gateway.py`, `test_auth.py` | 30 | Routing, proxying, error handling, JWT validation |
| Product Service | `test_product_service.py` | — | CRUD operations, search, validation |
| Order Service | `test_order_service.py` | 15 | Order creation, stock checks, cancellation, Kafka |
| Inventory Service | `test_inventory_service.py` | 20 | CRUD, stock check, reduce, restock, edge cases |
| Notification Service | `test_email_service.py`, `test_kafka_consumer.py` | 34 | Email templates, SMTP, Kafka routing, all 4 handlers |
| AI Service | `test_llm_clients.py`, `test_ai_services.py`, `test_product_client.py`, `test_kafka.py` | 44 | All 3 LLM providers, all 4 AI features, product client, Kafka |

**Total: 143+ unit tests across all services**

### Running Tests
```bash
cd <service-directory>
source venv/bin/activate
pytest -v
```

---

## 🐳 Infrastructure (Docker Compose)

| Service | Port | Purpose |
|---|---|---|
| MongoDB | 27017 | Product Service database |
| PostgreSQL | 5433 | Order + Inventory databases |
| Kafka | 9092 | Event streaming |
| Zookeeper | 2181 | Kafka coordination |
| Kafka UI | 8090 | Visual Kafka management |
| Keycloak | 8081 | OAuth2 / JWT identity provider |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Dashboards |
| Loki | 3100 | Log aggregation |
| Tempo | 3200 | Distributed tracing |

### Starting Infrastructure
```bash
cd Python-Microservices
docker-compose up -d
```

### Verifying Services
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

---

## 🚀 Running the Application

### Prerequisites
- macOS with Homebrew
- Python 3.12 (via Homebrew, **not** Anaconda)
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

# Terminal 6: API Gateway
cd api-gateway && source venv/bin/activate
python -m uvicorn app.main:app --port 9000 --loop asyncio
```

### Step 3 — Test via Gateway
```bash
# Health check
curl http://localhost:9000/health

# Add inventory
curl -X POST http://localhost:9000/api/inventory \
  -H "Content-Type: application/json" \
  -d '{"product_id": "prod-001", "product_name": "iPhone 15 Pro", "quantity": 100}'

# Place order (triggers full Kafka flow)
curl -X POST http://localhost:9000/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Yash Vyas",
    "customer_email": "yash@example.com",
    "items": [{
      "product_id": "prod-001",
      "product_name": "iPhone 15 Pro",
      "quantity": 1,
      "unit_price": 999.99
    }]
  }'

# AI chatbot
curl -X POST http://localhost:9000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What products do you have?"}'
```

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

---

## 🐛 Notable Issues & Fixes

| Issue | Root Cause | Fix |
|---|---|---|
| Anaconda interfering with async event loop | venv inherited Anaconda's sys.path | Removed Anaconda, used Homebrew Python |
| MongoDB auth failing from host to Docker | SCRAM auth broken over Docker TCP bridge on Mac | Disabled auth for local dev |
| `motor` + `pymongo` version incompatibility | Motor relied on removed PyMongo internals | Pinned compatible versions |
| PostgreSQL init script not running | Data volume already initialized | `docker-compose down -v` to reset |
| Port conflicts on Mac (8080, 5432) | Local processes occupying ports | Remapped to 8081, 5433 |
| SQLAlchemy async missing `greenlet` | Not auto-installed as dependency | Added to requirements.txt |
| Missing `__init__.py` files | Python can't find packages | Created in all directories |
| Gemini daily rate limit exhausted | Kafka burst + retry cascading | Switched to Groq, added throttling |
| Product Service response format mismatch | Returns dict not list | Handle both formats in client |
| Pydantic rejecting extra `.env` fields | Fields not declared in Settings | Added all fields to config.py |

---

## 🗺️ Build Roadmap

```
Phase 1 ✅ Infrastructure
  └── Docker Compose (Kafka, PostgreSQL, MongoDB, Keycloak, Observability)

Phase 2 ✅ Core Services
  ├── Product Service (MongoDB, Motor async)
  ├── Inventory Service (PostgreSQL, SQLAlchemy async)
  └── Order Service (PostgreSQL, httpx, aiokafka)

Phase 3 ✅ Async Layer
  └── Notification Service (Kafka consumer, Gmail SMTP)

Phase 4 ✅ AI Layer
  └── AI Service (Groq/Llama 3.3 70B, provider-agnostic, Kafka consumer + producer)

Phase 5 ✅ Gateway & Security
  └── API Gateway (routing, JWT validation via Keycloak, rate limiting)

Phase 6 🔲 Resilience
  ├── Circuit Breaker (pybreaker)
  ├── Retry + Backoff (tenacity)
  ├── Timeouts (httpx)
  └── Rate Limiting (slowapi) ✅ Done in Gateway

Phase 7 🔲 Observability
  └── Prometheus, Grafana, Loki, Tempo wiring

Phase 8 🔲 CI/CD
  └── GitHub Actions (lint → test → build → deploy)
```

---

## 📄 License

This project is built for learning and portfolio purposes.

---

## 👤 Author

**Yash Vyas**