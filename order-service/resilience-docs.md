# Resilience Patterns — Technical Documentation

## Overview

Phase 6 adds production-grade resilience patterns across the Order Service and Notification Service. These patterns ensure the system degrades gracefully when downstream services fail, prevents cascading failures, guarantees event delivery, and eliminates duplicate processing.

---

## Patterns Implemented

| Pattern | Service | Library | Purpose |
|---|---|---|---|
| **Outbox Pattern** | Order Service | PostgreSQL | Guaranteed Kafka event delivery |
| **Idempotency** | Notification Service | Redis `SET NX` | Prevents duplicate email sending |
| **Circuit Breaker** | Order Service | Custom (async-native) | Prevents cascading failures to Inventory |
| **Retry + Backoff** | Order Service | tenacity | Handles transient network failures |
| **Timeouts** | Order Service | httpx | Prevents indefinite waiting |

---

## 1. Outbox Pattern (Order Service)

### Problem
The original Order Service published events directly to Kafka after saving the order. If Kafka was down, the event was lost — the order was saved but no email was sent and no AI personalization happened.

### Solution
Save the event to an `outbox` table in the **same PostgreSQL transaction** as the order. A background worker polls the outbox and publishes to Kafka. If Kafka is down, events stay `PENDING` and are retried.

### Flow

```
Order Service:
  BEGIN TRANSACTION
    1. Save order to PostgreSQL        ✅
    2. Save event to outbox table      ✅ (same transaction — atomic)
  COMMIT

  Background worker (every 5 seconds):
    3. SELECT * FROM outbox WHERE status = 'PENDING'
    4. Publish each event to Kafka
    5. Mark as 'SENT' with timestamp
    6. Cleanup: DELETE events older than 7 days
```

### Outbox Table Schema

```sql
Table: outbox
┌──────────────────┬───────────────┬──────────────┐
│ id (UUID, PK)    │ topic         │ event_payload│
│ status (ENUM)    │ created_at    │ sent_at      │
└──────────────────┴───────────────┴──────────────┘

Status: PENDING → SENT
```

### Files Changed

| File | Change |
|---|---|
| `models/outbox.py` | **NEW** — Outbox SQLAlchemy model |
| `services/outbox_worker.py` | **NEW** — Background worker with polling + cleanup |
| `services/order_service.py` | **MODIFIED** — `_save_to_outbox()` replaces direct Kafka publish |
| `kafka/producer.py` | **MODIFIED** — Added generic `publish_event(topic, payload)` |
| `main.py` | **MODIFIED** — Starts outbox worker as background task |
| `config.py` | **MODIFIED** — Added `OUTBOX_POLL_INTERVAL_SECONDS`, `OUTBOX_RETENTION_DAYS` |

### Failure Scenarios

| Scenario | Outcome |
|---|---|
| Kafka is down when order placed | Order succeeds, event stays PENDING, retried when Kafka returns |
| Service crashes after DB commit | Event is in PostgreSQL, worker picks it up on restart |
| Worker crashes during publish | Event stays PENDING, retried next cycle |
| Worker publishes but crashes before marking SENT | Event re-published (consumers handle duplicates via idempotency) |

---

## 2. Redis Idempotency (Notification Service)

### Problem
The outbox pattern guarantees **at-least-once delivery** — the same event might be published twice (worker crash after publish, before marking SENT). The Notification Service would send duplicate emails.

### Solution
Before processing any event, check Redis using `SET NX` (set if not exists). If the key exists, the event is a duplicate and is skipped.

### Flow

```
Event arrives: ORD-001_ORDER_PLACED

Redis: SET processed:ORD-001_ORDER_PLACED "1" NX EX 604800
  → Returns True (new)  → process event, send email
  → Returns None (exists) → skip duplicate

Key auto-expires after 7 days (604800 seconds)
```

### Files Changed

| File | Change |
|---|---|
| `kafka/consumer.py` | **MODIFIED** — Added `_is_duplicate()` check using Redis before each handler |
| `config.py` | **MODIFIED** — Added `REDIS_HOST`, `REDIS_PORT`, `REDIS_IDEMPOTENCY_TTL` |
| `requirements.txt` | **MODIFIED** — Added `redis==5.2.1` |
| `docker-compose.yml` | **MODIFIED** — Added Redis 7.2 container |

### Why Redis over PostgreSQL for Idempotency

| Concern | Redis | PostgreSQL |
|---|---|---|
| Speed | <1ms per check | ~5ms per check |
| Auto cleanup | TTL expiry (built-in) | Needs cleanup job |
| Schema | No schema needed | Needs table + migration |
| Fit | Perfect for key-value checks | Overkill for simple flags |

### Failure Scenario — Redis Down

If Redis is unavailable, `_is_duplicate` returns `False` (fail-open) and the event is processed anyway. This means a duplicate might slip through if Redis is down — acceptable trade-off over blocking all events.

---

## 3. Circuit Breaker (Order → Inventory)

### Problem
When the Inventory Service is down, every order request waits for the HTTP call to time out (5 seconds), retries 3 times (with backoff), consuming resources for ~15 seconds per request. Under load, this cascades — the Order Service becomes unresponsive because all connections are waiting for a dead service.

### Solution
A circuit breaker tracks consecutive failures. After 5 failures, it "opens" and immediately rejects requests without making any HTTP call. After 30 seconds, it allows one test request through. If that succeeds, the circuit closes and normal operation resumes.

### State Machine

```
         5 consecutive failures
CLOSED ──────────────────────────────► OPEN
  ▲                                      │
  │                                      │ after 30 seconds
  │         test request succeeds        ▼
  └──────────────────────────────── HALF-OPEN
                                         │
                                         │ test request fails
                                         ▼
                                       OPEN
```

### Implementation — Custom Async-Native Circuit Breaker

We built a custom `CircuitBreaker` class instead of using `pybreaker` because `pybreaker`'s `call_async` method depends on Tornado's `gen.coroutine`, which is broken in modern Python 3.12 with native async/await.

```python
class CircuitBreaker:
    def __init__(self, name, fail_max=5, reset_timeout=30):
        ...

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError("Circuit is open")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise
```

### How All Three Patterns Work Together

```
Request comes in: POST /api/orders

1. CIRCUIT BREAKER — is the circuit OPEN?
   YES → CircuitBreakerError → 503 instantly (no HTTP call, no waiting)
   NO  → proceed

2. RETRY (tenacity) — try the HTTP call
   Attempt 1 → fail → circuit breaker counts failure #N → wait 1s
   Attempt 2 → fail → circuit breaker counts failure #N+1 → wait 2s
   Attempt 3 → fail → circuit breaker counts failure #N+2 → raise
   (After 5 total failures across requests → circuit OPENS)

3. TIMEOUT (httpx) — each HTTP attempt has:
   connect: 3s, read: 5s, write: 3s, pool: 5s
```

### Configuration

| Setting | Value | Purpose |
|---|---|---|
| `fail_max` | 5 | Failures before circuit opens |
| `reset_timeout` | 30 seconds | Time before half-open test |
| `retry attempts` | 3 | Tenacity retry count |
| `retry backoff` | 1s, 2s, 4s | Exponential backoff |
| `connect timeout` | 3 seconds | TCP connection timeout |
| `read timeout` | 5 seconds | Response read timeout |

### Excluded Exceptions

Business errors like `HTTPException(404)` (product not found) do not count as circuit breaker failures. Only infrastructure errors (connection refused, timeout) trip the circuit.

### Files

| File | Purpose |
|---|---|
| `clients/circuit_breaker.py` | **NEW** — Custom async circuit breaker |
| `clients/inventory_client.py` | **MODIFIED** — Uses circuit breaker + retry + timeout |

---

## Testing

### `test_outbox.py` — 10 tests

| Area | Tests |
|---|---|
| Process pending | Publishes to Kafka, marks as SENT, no events skips, Kafka failure keeps PENDING, multiple events, partial failure |
| Cleanup | Deletes old SENT events, skips if none |
| Model | Default status PENDING, valid JSON payload |

### `test_circuit_breaker.py` — 20 tests

| Area | Tests |
|---|---|
| Initial state | Closed, fail counter zero |
| Success | Returns result, keeps closed, resets fail counter |
| Failure | Increments counter, raises original exception, stays closed below threshold |
| Circuit opens | Opens at fail_max, rejects immediately, doesn't call function |
| Half-open | Transitions after timeout, success closes, failure reopens |
| Exclude | Excluded exceptions not counted, still raised, non-excluded counted |
| Args | Passes positional args, passes keyword args |

### `test_kafka_consumer.py` — 23 tests (Notification Service)

| New Tests | Description |
|---|---|
| Duplicate detection | Each handler skips when `_is_duplicate` returns True |
| `_is_duplicate` | New event → False, existing → True, Redis down → False (fail-open), correct key format |

---

## Issues Encountered

### Issue 1 — pybreaker Broken with Python 3.12 Async

**What happened:** `pybreaker.call_async()` crashed with `NameError: name 'gen' is not defined`.

**Root cause:** pybreaker's async support uses Tornado's `gen.coroutine` decorator, which requires Tornado as a dependency. Without Tornado installed, it crashes. Even with Tornado, `gen.coroutine` is a legacy pattern incompatible with native `async/await`.

**Fix:** Built a custom `CircuitBreaker` class using native Python `async/await`. No external dependencies, ~80 lines of code, fully tested.

### Issue 2 — Local Redis Conflicting with Docker Redis

**What happened:** Python wrote idempotency keys to Redis successfully, but `docker exec redis-cli KEYS` showed an empty array.

**Root cause:** Two Redis instances were running — a local Homebrew Redis on `localhost:6379` and the Docker Redis container also on port 6379. Python connected to the local one, Docker CLI checked the container one.

**Fix:** Stopped the local Redis with `brew services stop redis`. Verified only Docker Redis was listening on 6379 with `lsof -i :6379`.

### Issue 3 — ConnectError Escaping to 500

**What happened:** When all 3 tenacity retries were exhausted, the final `httpx.ConnectError` propagated to FastAPI as an unhandled exception, returning 500 instead of 503.

**Fix:** Added a try/except wrapper in `order_service.py` around the `check_stock` call to catch any exception after retries are exhausted and convert to `HTTPException(503)`.

---

## Key Lessons Learned

**Outbox pattern requires idempotent consumers.** At-least-once delivery means duplicates are possible. Every Kafka consumer must handle duplicates — Redis `SET NX` is the simplest approach.

**Circuit breakers prevent cascading failures.** Without the breaker, a down Inventory Service causes the Order Service to become unresponsive (all threads waiting on timeouts). With the breaker, failures are instant after the threshold.

**Don't retry non-idempotent operations.** `check_stock` (read) is safe to retry. `reduce_stock` (write) is not — retrying could reduce stock twice. Only reads get the retry decorator.

**Build your own circuit breaker when libraries fail.** pybreaker's async support is broken. A custom implementation in ~80 lines works perfectly with native async/await and has no external dependencies.

**Redis is the right tool for idempotency checks.** `SET NX` with TTL gives you atomic duplicate detection with automatic cleanup. No schema, no migrations, sub-millisecond performance.

**Resilience patterns compose.** Retry → Circuit Breaker → Timeout work together as layers. Each handles a different failure mode, and they don't interfere with each other.
