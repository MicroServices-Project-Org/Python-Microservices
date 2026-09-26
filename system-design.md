# 🏗️ FastAPI Microservices + AI — Production System Design

---

## 1. SERVICE ARCHITECTURE

```
                        ┌─────────────────┐
                        │   Angular/React  │
                        │    Frontend      │
                        └────────┬────────┘
                                 │ HTTPS
                        ┌────────▼────────┐
                        │   API Gateway   │  ← Single entry point
                        │   (FastAPI)     │  ← Rate limiting
                        │   Port: 9000    │  ← JWT validation
                        └──┬──┬──┬──┬────┘
                           │  │  │  │
          ┌────────────────┘  │  │  └─────────────────┐
          │             ┌─────┘  └─────┐               │
          ▼             ▼              ▼                ▼
  ┌──────────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐
  │   Product    │ │  Order   │ │  Inventory   │ │    AI    │
  │   Service   │ │  Service │ │   Service    │ │  Service │
  │  Port: 8001  │ │Port: 8002│ │  Port: 8003  │ │Port: 8005│
  └──────┬───────┘ └────┬─────┘ └──────────────┘ └────┬─────┘
         │              │  REST call to Inventory       │
         │              │ ──────────────────────►       │
    MongoDB          PostgreSQL                    OpenAI API
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
              └────────────────────-─┘
               AI sends personalized
               content to Notification

  ┌─────────────────────────────────────────────────┐
  │              Keycloak (Port: 8080)              │
  │         OAuth2 / JWT Identity Provider          │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │           Observability Stack                   │
  │  Prometheus → Grafana │ Loki (logs) │ Tempo     │
  └─────────────────────────────────────────────────┘
```

---

## 2. SERVICE RESPONSIBILITIES

| Service | Responsibility | DB | Port |
|---|---|---|---|
| API Gateway | Routing, auth, rate limiting | None | 9000 |
| Product Service | CRUD for product catalog | MongoDB | 8001 |
| Order Service | Place & manage orders | PostgreSQL | 8002 |
| Inventory Service | Stock management | PostgreSQL | 8003 |
| Notification Service | Email/SMS via events | None | 8004 |
| AI Service | Recommendations, chat, suggestions | None (stateless) | 8005 |

---

## 3. DATABASE SCHEMA DESIGN

### 📦 Product Service — MongoDB

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

---

### 🛒 Order Service — PostgreSQL

```sql
Table: orders
┌─────────────────┬──────────────────┬──────────────┐
│ id (UUID, PK)   │ order_number     │ customer_id  │
│ customer_email  │ customer_name    │ total_amount │
│ status          │ created_at       │ updated_at   │
└─────────────────┴──────────────────┴──────────────┘
  status ENUM: PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED

Table: order_items
┌───────────────────┬──────────────────┬─────────────────┐
│ id (UUID, PK)     │ order_id (FK)    │ product_id      │
│ product_name      │ quantity         │ unit_price      │
│ total_price       │                  │                 │
└───────────────────┴──────────────────┴─────────────────┘
```

---

### 📦 Inventory Service — PostgreSQL

```sql
Table: inventory
┌───────────────────┬──────────────────┬─────────────────┐
│ id (UUID, PK)     │ product_id       │ product_name    │
│ quantity          │ reserved_qty     │ updated_at      │
└───────────────────┴──────────────────┴─────────────────┘

Table: inventory_transactions
┌───────────────────┬──────────────────┬─────────────────┐
│ id (UUID, PK)     │ product_id (FK)  │ change_qty      │
│ type (IN/OUT)     │ reason           │ created_at      │
└───────────────────┴──────────────────┴─────────────────┘
```

---

## 4. API CONTRACTS

### 🔵 API Gateway — `/api/*`
| Method | Path | Proxies To |
|---|---|---|
| `*` | `/api/products/**` | product-service:8001 |
| `*` | `/api/orders/**` | order-service:8002 |
| `*` | `/api/inventory/**` | inventory-service:8003 |
| `*` | `/api/ai/**` | ai-service:8005 |

---

### 📦 Product Service
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/products` | List all products |
| `GET` | `/api/products/{id}` | Get product by ID |
| `POST` | `/api/products` | Create product |
| `PUT` | `/api/products/{id}` | Update product |
| `DELETE` | `/api/products/{id}` | Delete product |
| `GET` | `/api/products/search?q=` | Search products |

---

### 🛒 Order Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/orders` | Place a new order |
| `GET` | `/api/orders/{id}` | Get order by ID |
| `GET` | `/api/orders/user/{email}` | Orders by customer |
| `PATCH` | `/api/orders/{id}/status` | Update order status |
| `DELETE` | `/api/orders/{id}` | Cancel order |

**POST /api/orders — Request Body:**
```json
{
  "customer_name": "Yash",
  "customer_email": "yash@example.com",
  "items": [
    {
      "product_id": "abc123",
      "product_name": "iPhone 15",
      "quantity": 1,
      "unit_price": 999.99
    }
  ]
}
```

---

### 📦 Inventory Service
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/inventory/{product_id}` | Check stock |
| `POST` | `/api/inventory` | Add inventory item |
| `PATCH` | `/api/inventory/{product_id}/reduce` | Reduce stock |
| `PATCH` | `/api/inventory/{product_id}/restock` | Restock item |

---

### 🤖 AI Service
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/chat` | Shopping assistant chatbot |
| `GET` | `/api/ai/recommendations` | Product recommendations |
| `POST` | `/api/ai/suggest` | Natural language product search |
| `POST` | `/api/ai/notify/personalize` | Personalize notification content |

**POST /api/ai/chat — Request:**
```json
{
  "message": "I'm looking for a gift under $100",
  "history": [
    { "role": "user", "content": "Hi" },
    { "role": "assistant", "content": "Hello! How can I help?" }
  ]
}
```

**GET /api/ai/recommendations?product_name=iPhone&category=Electronics**

**POST /api/ai/suggest — Request:**
```json
{
  "query": "something warm for winter under $50"
}
```

---

## 5. KAFKA EVENT FLOW

```
Order Service                 Kafka                  Consumers
─────────────           ──────────────────     ─────────────────────────
                        Topic: order-placed
PlaceOrder()  ───────►  { order_number,     ──► Notification Service
                          customer_name,         (sends email)
                          customer_email,
                          items[],           ──► AI Service
                          total_amount }          (generates personalized
                                                   email body, sends back
                                                   to Notification Service)
```

### Kafka Topics

| Topic | Producer | Consumers | Purpose |
|---|---|---|---|
| `order-placed` | Order Service | Notification, AI Service | New order created |
| `order-cancelled` | Order Service | Notification, Inventory | Order cancelled |
| `ai-notification-ready` | AI Service | Notification Service | Personalized email ready |

### Event Schema — `order-placed`
```json
{
  "event_type": "ORDER_PLACED",
  "timestamp": "2025-02-20T10:00:00Z",
  "order_number": "ORD-20250220-001",
  "customer_name": "Yash",
  "customer_email": "yash@example.com",
  "total_amount": 999.99,
  "items": [
    {
      "product_name": "iPhone 15 Pro",
      "quantity": 1,
      "price": 999.99
    }
  ]
}
```

---

## 6. AI INTEGRATION FLOW

```
┌──────────────────────────────────────────────────────────┐
│                      AI Service                          │
│                                                          │
│  ┌─────────────────┐   ┌──────────────────────────────┐ │
│  │  REST Endpoints │   │     Kafka Consumer           │ │
│  │                 │   │                              │ │
│  │ /chat           │   │  Topic: order-placed         │ │
│  │ /recommendations│   │  → build personalized prompt │ │
│  │ /suggest        │   │  → call OpenAI               │ │
│  └────────┬────────┘   │  → publish ai-notification   │ │
│           │            └──────────────────────────────┘ │
│           ▼                         │                    │
│  ┌────────────────────────────────┐ │                    │
│  │       OpenAI Client            │ │                    │
│  │  (gpt-4o via openai-python)   │ │                    │
│  │                                │ │                    │
│  │  System Prompt: "You are a     │ │                    │
│  │  helpful shopping assistant    │ │                    │
│  │  for our e-commerce store..."  │ │                    │
│  └────────────────────────────────┘ │                    │
└──────────────────────────────────────────────────────────┘
```

### AI Features Breakdown

| Feature | Trigger | Input | Output |
|---|---|---|---|
| Recommendations | REST call | product name + category | List of 5 products |
| Chatbot | REST call | message + history | AI reply |
| Smart Search | REST call | natural language query | matched categories/tags |
| Notification Personalization | Kafka event | order details | personalized email body |

---

## 7. FOLDER / PROJECT STRUCTURE

```
fastapi-microservices/
│
├── api-gateway/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── auth/
│   │   │   └── keycloak.py       # JWT validation
│   │   └── middleware/
│   │       └── rate_limit.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── product-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py           # Motor (async MongoDB)
│   │   ├── models/
│   │   │   └── product.py        # MongoDB document model
│   │   ├── schemas/
│   │   │   └── product.py        # Pydantic request/response
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
│   │   ├── database.py           # SQLAlchemy + PostgreSQL
│   │   ├── models/
│   │   │   └── order.py          # SQLAlchemy ORM models
│   │   ├── schemas/
│   │   │   └── order.py          # Pydantic schemas
│   │   ├── routes/
│   │   │   └── order_routes.py
│   │   ├── services/
│   │   │   └── order_service.py
│   │   └── kafka/
│   │       └── producer.py       # aiokafka producer
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── inventory-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
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
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── kafka/
│   │   │   └── consumer.py       # aiokafka consumer
│   │   └── services/
│   │       └── email_service.py  # SMTP / SendGrid
│   ├── Dockerfile
│   └── requirements.txt
│
├── ai-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routes/
│   │   │   └── ai_routes.py
│   │   ├── services/
│   │   │   ├── recommendation.py
│   │   │   ├── chatbot.py
│   │   │   ├── suggestion.py
│   │   │   └── notification_ai.py
│   │   └── kafka/
│   │       ├── consumer.py       # Consumes order-placed
│   │       └── producer.py       # Publishes ai-notification-ready
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker-compose.yml            # Full local dev environment
├── k8s/
│   ├── infrastructure.yaml       # Kafka, DBs, Keycloak, Grafana
│   └── applications.yaml         # All 6 services
└── README.md
```

---

## 8. RESILIENCE PATTERNS

### Libraries
```
pybreaker    # Circuit Breaker
tenacity     # Retry with exponential backoff
slowapi      # Rate limiting (API Gateway)
httpx        # Built-in timeout on all HTTP calls
```

### Pattern Application Map

| Pattern | Library | Applied At | Fallback |
|---|---|---|---|
| Circuit Breaker | `pybreaker` | Order → Inventory | Return "service unavailable" |
| Retry + Backoff | `tenacity` | Order → Inventory, AI → OpenAI | Raise after max retries |
| Timeout | `httpx` | All inter-service calls | Raise timeout exception |
| Rate Limiter | `slowapi` | API Gateway | 429 Too Many Requests |

### Circuit Breaker State Flow
```
         requests failing > threshold
CLOSED ──────────────────────────────► OPEN
  ▲                                      │
  │                                      │ after reset_timeout
  │         test request succeeds        ▼
  └──────────────────────────────── HALF-OPEN
```
- **CLOSED** → normal operation, requests pass through
- **OPEN** → circuit tripped, requests fail immediately (no waiting)
- **HALF-OPEN** → one test request allowed, if it succeeds → back to CLOSED

### Retry Strategy (tenacity)
```
Attempt 1 → fail → wait 1s
Attempt 2 → fail → wait 2s
Attempt 3 → fail → wait 4s
Attempt 4 → fail → wait 8s (max)
Attempt 5 → fail → raise exception
```

### Timeout Config (httpx)
```
connect_timeout  = 3s   # time to establish connection
read_timeout     = 5s   # time to wait for response
write_timeout    = 3s   # time to send request body
pool_timeout     = 5s   # time to wait for a connection from pool
```

---

## 9. TESTING STRATEGY

### Unit Tests (per service)
| What | Tool | Purpose |
|---|---|---|
| Route handlers | `pytest` | Test request/response logic |
| Service layer | `pytest` + `unittest.mock` | Test business logic in isolation |
| Pydantic schemas | `pytest` | Validate input/output models |

### Integration Tests (per service)
| What | Tool | Purpose |
|---|---|---|
| DB operations | `pytest` + `testcontainers-python` | Spin up real PostgreSQL/MongoDB in Docker |
| Kafka events | `pytest` + `testcontainers-python` | Spin up real Kafka, test produce/consume |
| REST endpoints | `httpx` + `pytest` | Full request cycle against real DB |
| Inter-service calls | `respx` (mock HTTP) | Mock other services' REST responses |

### Test Structure (per service)
```
<service>/
└── tests/
    ├── unit/
    │   ├── test_routes.py
    │   └── test_services.py
    └── integration/
        ├── test_db.py
        └── test_kafka.py
```

### Key Libraries
```
pytest                    # test runner
pytest-asyncio            # async test support for FastAPI
httpx                     # async HTTP client for endpoint testing
testcontainers-python     # spin up real Docker containers in tests
respx                     # mock external HTTP calls (inter-service)
unittest.mock             # mock OpenAI calls in AI service tests
coverage                  # code coverage reporting
```

---

## 10. CI/CD — GITHUB ACTIONS FLOW

```
Push / PR to main
       │
       ▼
┌─────────────────────────────────────────────────────┐
│                   CI Pipeline                       │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌────────────────┐  │
│  │  Lint &  │──►│  Unit    │──►│  Integration   │  │
│  │  Format  │   │  Tests   │   │  Tests         │  │
│  │(ruff,    │   │(pytest)  │   │(testcontainers)│  │
│  │ black)   │   │          │   │                │  │
│  └──────────┘   └──────────┘   └───────┬────────┘  │
│                                         │           │
│                              ┌──────────▼────────┐  │
│                              │  Coverage Report  │  │
│                              │  (min 80%)        │  │
│                              └──────────┬────────┘  │
└─────────────────────────────────────────┼───────────┘
                                          │ (only on merge to main)
                                          ▼
┌─────────────────────────────────────────────────────┐
│                   CD Pipeline                       │
│                                                     │
│  ┌──────────────┐   ┌──────────────┐                │
│  │ Build Docker │──►│ Push to      │                │
│  │ Images       │   │ Docker Hub   │                │
│  │ (per service)│   │ (tagged)     │                │
│  └──────────────┘   └──────┬───────┘                │
│                             │                       │
│                    ┌────────▼───────┐               │
│                    │ Deploy to K8s  │               │
│                    │ (Kind / EKS)   │               │
│                    └────────────────┘               │
└─────────────────────────────────────────────────────┘
```

### GitHub Actions Workflows
| File | Trigger | Purpose |
|---|---|---|
| `ci.yml` | Every push / PR | Lint, unit tests, integration tests, coverage |
| `cd.yml` | Merge to `main` | Build images, push to Docker Hub, deploy to K8s |
| `pr-check.yml` | PR opened | Fast lint + unit tests only (quick feedback) |

### Branch Strategy
```
main          ← production-ready, protected branch
  └── develop ← integration branch
        └── feature/product-service
        └── feature/order-service
        └── feature/ai-service
        └── fix/inventory-bug
```

---

## 11. DOCKER COMPOSE SERVICES

```yaml
Services spun up:
  - api-gateway        (port 9000)
  - product-service    (port 8001)
  - order-service      (port 8002)
  - inventory-service  (port 8003)
  - notification-service (port 8004)
  - ai-service         (port 8005)
  - mongodb            (port 27017)
  - postgres           (port 5432)
  - kafka + zookeeper  (port 9092)
  - keycloak           (port 8080)
  - prometheus         (port 9090)
  - grafana            (port 3000)
  - loki               (port 3100)
  - tempo              (port 3200)
```

---

## 12. INTER-SERVICE COMMUNICATION SUMMARY

```
Synchronous (REST/HTTP):
  Gateway        → All Services
  Order Service  → Inventory Service (stock check before confirming order)

Asynchronous (Kafka):
  Order Service  → [order-placed topic]      → Notification Service
  Order Service  → [order-placed topic]      → AI Service
  AI Service     → [ai-notification-ready]   → Notification Service
  Order Service  → [order-cancelled topic]   → Notification Service, Inventory Service
  Product Svc    → [product-updated topic]   → Search Service, AI Service
```

---

## 13. SECURITY FLOW

```
1. User logs in via Keycloak → gets JWT access token
2. Frontend sends JWT in Authorization header:
   Authorization: Bearer <token>
3. API Gateway intercepts → validates JWT with Keycloak public key
4. If valid → strips auth header, forwards request to target service
5. If invalid → 401 Unauthorized, request blocked at gateway
6. Services trust all requests from Gateway (internal network only)
```

---

## 14. BUILD ORDER (Recommended)

Build services in this order to avoid dependency issues:

```
Phase 1 — Infrastructure
  └── Set up docker-compose (Kafka, DBs, Keycloak)

Phase 2 — Core Services
  ├── Inventory Service  (no dependencies)
  ├── Product Service    (no dependencies)
  └── Order Service      (depends on Inventory via REST + Kafka)

Phase 3 — Async Layer
  └── Notification Service (depends on Kafka)

Phase 4 — AI Layer
  └── AI Service (depends on Kafka + OpenAI API)

Phase 5 — Gateway & Security
  └── API Gateway (depends on all services + Keycloak)

Phase 5 — Resilience
  └── Circuit Breaker on Order → Inventory (pybreaker)
  └── Retry + Backoff on AI → OpenAI (tenacity)
  └── Timeouts on all HTTP calls (httpx)
  └── Rate limiting on API Gateway (slowapi)

Phase 6 — Observability
  └── Wire Prometheus, Grafana, Loki, Tempo

Phase 7 — Testing
  └── Unit tests per service (pytest + mocks)
  └── Integration tests (testcontainers-python)

Phase 8 — CI/CD
  └── GitHub Actions CI (lint → unit → integration → coverage)
  └── GitHub Actions CD (build → push Docker Hub → deploy K8s)
```
