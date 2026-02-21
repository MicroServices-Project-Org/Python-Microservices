# Order Service — Technical Documentation

## Overview

The Order Service is the most complex service in the FastAPI Microservices project. It manages customer orders, orchestrates synchronous stock verification with the Inventory Service, and publishes asynchronous events to Kafka for downstream consumers like the Notification and AI services.

---

## Tech Stack Decisions

### PostgreSQL over MongoDB
Orders are relational by nature — an order has many items, each linked to a product. PostgreSQL's foreign keys, JOINs, and ACID transactions are the right fit. An order and its items must either both save or both fail — atomicity is critical here.

### SQLAlchemy with Relationships
Unlike the Inventory Service which has a single flat table, the Order Service has two related tables (`orders` and `order_items`). SQLAlchemy's `relationship()` and `selectinload()` handle this cleanly, loading order items in a single optimized query rather than N+1 queries.

### httpx for Inter-Service Communication
`httpx` is the async HTTP client used to call the Inventory Service. It supports connection timeouts, read timeouts, and integrates cleanly with FastAPI's async event loop. The synchronous `requests` library would block the event loop.

### tenacity for Retry Logic
Transient network failures between microservices are normal in production. `tenacity` provides retry with exponential backoff on the Inventory Service call. If the Inventory Service has a brief hiccup, the order request retries automatically up to 3 times rather than failing immediately.

### aiokafka for Event Publishing
`aiokafka` is the async Kafka client. After an order is confirmed, an `order-placed` event is published to Kafka. The Notification Service and AI Service consume this event independently. This decouples order creation from email sending — if the Notification Service is down, orders still succeed.

### Non-blocking Kafka
The Kafka publish is intentionally non-critical. If Kafka is unavailable, the order is still saved and confirmed. The `publish_order_placed` function catches exceptions and logs them rather than raising. This follows the pattern of "reserve best-effort side effects" — the core business transaction should not fail because of an observability or notification system.

---

## Project Structure

```
order-service/
├── app/
│   ├── main.py                     # FastAPI app, lifespan, table creation
│   ├── config.py                   # Settings from .env
│   ├── database.py                 # SQLAlchemy async engine and session
│   ├── models/
│   │   └── order.py                # Order, OrderItem SQLAlchemy models
│   ├── schemas/
│   │   └── order.py                # Pydantic request/response schemas
│   ├── routes/
│   │   └── order_routes.py         # API endpoint definitions
│   ├── services/
│   │   └── order_service.py        # Business logic and orchestration
│   ├── clients/
│   │   └── inventory_client.py     # HTTP client for Inventory Service
│   └── kafka/
│       └── producer.py             # Kafka event publisher
├── tests/
│   └── unit/
│       └── test_order_service.py
├── Dockerfile
└── requirements.txt
```

---

## Database Schema

```sql
Table: orders
┌──────────────────┬────────────────┬──────────────────┐
│ id (UUID, PK)    │ order_number   │ customer_name    │
│ customer_email   │ total_amount   │ status (ENUM)    │
│ created_at       │ updated_at     │                  │
└──────────────────┴────────────────┴──────────────────┘

OrderStatus ENUM: PENDING | CONFIRMED | SHIPPED | DELIVERED | CANCELLED

Table: order_items
┌──────────────────┬────────────────┬──────────────────┐
│ id (UUID, PK)    │ order_id (FK)  │ product_id       │
│ product_name     │ quantity       │ unit_price       │
│ total_price      │                │                  │
└──────────────────┴────────────────┴──────────────────┘
```

**Why store `product_name` in order_items?**
Product names can change over time. By storing the name at order time, the order history always reflects what the customer actually ordered, not the current product name.

---

## Order Flow

```
Client → POST /api/orders
           │
           ▼
    1. Check stock for each item
       GET /api/inventory/{id}/check?quantity=N
           │
           ▼
    2. If all in stock → save order (PostgreSQL)
           │
           ▼
    3. Save order items (PostgreSQL)
           │
           ▼
    4. Reduce stock for each item
       PATCH /api/inventory/{id}/reduce
           │
           ▼
    5. Publish order-placed event (Kafka)
           │
           ▼
    6. Return 201 Created with order details
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/orders` | Place a new order |
| `GET` | `/api/orders` | Get all orders |
| `GET` | `/api/orders/{order_id}` | Get order by ID |
| `GET` | `/api/orders/user/{email}` | Get orders by customer email |
| `PATCH` | `/api/orders/{order_id}/status` | Update order status |
| `PATCH` | `/api/orders/{order_id}/cancel` | Cancel an order |
| `GET` | `/health` | Health check |

---

## Kafka Event Schema

Topic: `order-placed`

```json
{
  "event_type": "ORDER_PLACED",
  "timestamp": "2026-02-21T03:02:36.792213Z",
  "order_number": "ORD-20260221-6BA0A415",
  "customer_name": "Yash Vyas",
  "customer_email": "yash@example.com",
  "total_amount": 1999.98,
  "items": [
    {
      "product_id": "prod-001",
      "product_name": "iPhone 15 Pro",
      "quantity": 2,
      "price": 999.99
    }
  ]
}
```

Consumed by:
- **Notification Service** → sends confirmation email
- **AI Service** → generates personalized notification content

---

## Resilience Patterns

### Retry with Exponential Backoff (tenacity)
Applied on the Inventory Service stock check:
```
Attempt 1 → fail → wait 1s
Attempt 2 → fail → wait 2s
Attempt 3 → fail → raise HTTPException 503
```
Only retries on `httpx.TransportError` (network-level failures), not on business errors like 404 or 400.

### Timeout Configuration (httpx)
```
connect_timeout = 3s   # time to establish TCP connection
read_timeout    = 5s   # time to wait for response body
write_timeout   = 3s   # time to send request body
pool_timeout    = 5s   # time to acquire connection from pool
```

### Non-critical Kafka
Kafka publish failure does not fail the order. The order is saved to PostgreSQL first, then the event is published. If Kafka is down, the order succeeds and the event is lost — acceptable for a portfolio project. In production, an outbox pattern would guarantee delivery.

---

## Environment Variables

```
APP_NAME=order-service
APP_PORT=8002
POSTGRES_USER=admin
POSTGRES_PASSWORD=password
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=order_db
INVENTORY_SERVICE_URL=http://localhost:8003
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_ORDER_TOPIC=order-placed
```

---

## Unit Tests — What's Covered

| Test | Description |
|---|---|
| `test_create_order_success` | Happy path order creation |
| `test_create_order_calculates_total_correctly` | 2 × 999.99 = 1999.98 |
| `test_create_order_multi_item_total` | Multiple items totaled correctly |
| `test_create_order_insufficient_stock_raises_400` | Out of stock → 400 |
| `test_create_order_checks_all_items` | All items checked, not just first |
| `test_create_order_stops_on_first_out_of_stock` | Stops early on failure |
| `test_create_order_reduces_stock_for_all_items` | Stock reduced for each item |
| `test_create_order_publishes_kafka_event` | Event published with correct fields |
| `test_create_order_generates_unique_order_number` | No duplicate order numbers |
| `test_create_order_status_is_confirmed` | Status set to CONFIRMED |
| `test_get_order_success` | Fetch by ID |
| `test_get_order_not_found_raises_404` | Missing order → 404 |
| `test_get_order_invalid_id_raises_400` | Bad UUID → 400 |
| `test_cancel_shipped_order_raises_400` | Cannot cancel shipped orders |
| `test_cancel_delivered_order_raises_400` | Cannot cancel delivered orders |

---

## Key Lessons Learned

**Mock both external dependencies in unit tests.** The Order Service calls Inventory Service (HTTP) and Kafka. Both must be mocked in unit tests using `unittest.mock.patch` so tests run without any running services.

**Kafka should be non-blocking for order creation.** Publishing an event is a side effect — it should never fail the core business transaction. Wrap Kafka calls in try/except and log failures rather than raising.

**Store product names at order time.** Product names change. Snapshoting the name in `order_items` preserves order history accurately.

**Use `selectinload` to avoid N+1 queries.** Loading order items with `selectinload(Order.items)` fetches all items in a single SQL query instead of one query per order.
