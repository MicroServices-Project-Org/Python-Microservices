# API Gateway — Technical Documentation

## Overview

The API Gateway is the sixth and final microservice in the FastAPI Microservices project. It serves as the single entry point for all client requests, handling routing to downstream services, JWT authentication via Keycloak, and rate limiting. No client ever communicates directly with a microservice — all traffic flows through the gateway on port 9000.

---

## Tech Stack Decisions

### FastAPI as a Reverse Proxy
Rather than using a dedicated reverse proxy like Nginx or Kong, the gateway is built with FastAPI and httpx. This keeps the entire project in Python with a consistent tech stack, makes JWT validation trivial via FastAPI dependencies, and allows custom logic (rate limiting per route, header stripping) without learning a separate configuration language.

### httpx with Shared AsyncClient
A single `httpx.AsyncClient` is created during the lifespan and reused for all proxy requests. This enables connection pooling — the gateway maintains persistent TCP connections to downstream services rather than opening a new connection per request. The client is configured with timeouts (3s connect, 10s read) to prevent slow services from blocking the gateway.

### PyJWT for Token Validation
PyJWT with the `cryptography` extra (`PyJWT[crypto]`) handles RS256 JWT validation. The gateway fetches Keycloak's public keys via the JWKS endpoint and caches the `PyJWKClient` instance — keys are only fetched once, not on every request.

### slowapi for Rate Limiting
`slowapi` wraps the popular `limits` library and integrates natively with FastAPI. It uses client IP as the rate limit key. AI routes get a stricter limit (15/minute) than standard CRUD routes (60/minute) because LLM calls are expensive.

### AUTH_ENABLED Feature Flag
Same pattern as `EMAIL_ENABLED` in the Notification Service. When `AUTH_ENABLED=false` (default), the gateway returns a dummy user payload and skips JWT validation entirely. This means developers can test the full system without configuring Keycloak. Authentication is enabled by setting `AUTH_ENABLED=true` in `.env`.

### Authorization Header Stripping
The gateway validates the JWT and then strips the Authorization header before forwarding to downstream services. Services trust all requests from the gateway — they don't need to validate tokens themselves. This follows the "trust the internal network" pattern used in production microservice architectures.

---

## Project Structure

```
api-gateway/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, proxy routes, lifespan
│   ├── config.py                # Settings (service URLs, Keycloak, rate limits)
│   ├── auth/
│   │   ├── __init__.py
│   │   └── keycloak.py          # JWT validation via Keycloak JWKS
│   └── middleware/
│       ├── __init__.py
│       └── rate_limit.py        # slowapi rate limiter
├── tests/
│   ├── __init__.py
│   └── unit/
│       ├── __init__.py
│       ├── test_gateway.py      # 21 tests — routing, proxying, errors
│       └── test_auth.py         # 9 tests — JWT validation
├── pytest.ini
├── Dockerfile
├── requirements.txt
└── .env
```

### Why No Models, Schemas, or Services Folders?
The API Gateway has no business logic, no database, and no data models. It is purely a routing and security layer. Requests are forwarded as-is to downstream services — the gateway does not transform, validate, or persist any data.

---

## Routing Architecture

```
Client (Browser / Mobile / Postman)
         │
         │ HTTPS / HTTP
         ▼
┌─────────────────────────────────┐
│       API Gateway (:9000)       │
│                                 │
│  1. Rate limit check            │
│  2. JWT validation (Keycloak)   │
│  3. Strip Authorization header  │
│  4. Proxy to downstream service │
└────────┬──┬──┬──┬───────────────┘
         │  │  │  │
         ▼  ▼  ▼  ▼
     :8001 :8002 :8003 :8005
     Prod   Ord   Inv    AI
```

### Route Mapping

| Gateway Path | Downstream Service | Port | Rate Limit |
|---|---|---|---|
| `/api/products/**` | Product Service | 8001 | 60/minute |
| `/api/orders/**` | Order Service | 8002 | 60/minute |
| `/api/inventory/**` | Inventory Service | 8003 | 60/minute |
| `/api/ai/**` | AI Service | 8005 | 15/minute |
| `/health` | Gateway itself | 9000 | None |

---

## Security Flow

```
1. User logs in via Keycloak → gets JWT access token
2. Client sends JWT in Authorization header:
   Authorization: Bearer <token>
3. Gateway intercepts → validates JWT with Keycloak public keys
4. If valid → strips auth header, forwards request to target service
5. If invalid → 401 Unauthorized, request blocked at gateway
6. If expired → 403 Forbidden
7. Services trust all requests from Gateway (internal network only)
```

### JWT Validation Details
- Algorithm: RS256 (asymmetric — Keycloak signs, gateway verifies)
- Keys: Fetched from Keycloak JWKS endpoint, cached in memory
- Checks: Signature, expiration, audience (must match `KEYCLOAK_CLIENT_ID`), issuer (must match Keycloak realm URL)

---

## Error Handling

The gateway translates downstream failures into appropriate HTTP responses:

| Scenario | Gateway Response | Status Code |
|---|---|---|
| Downstream service is down | `Service unavailable: {service}` | 503 |
| Downstream service is slow | `Service timeout: {service}` | 504 |
| Downstream returns 4xx/5xx | Forwarded as-is | Same as downstream |
| Invalid/missing JWT | `Missing or invalid Authorization header` | 401 |
| Expired JWT | `Token has expired` | 403 |
| Rate limit exceeded | `Rate limit exceeded` | 429 |

---

## Rate Limiting

| Route Group | Limit | Reason |
|---|---|---|
| Products, Orders, Inventory | 60 requests/minute | Standard CRUD operations |
| AI | 15 requests/minute | LLM calls are expensive and have their own rate limits |

Rate limits are applied per client IP via `slowapi`. When exceeded, the gateway returns `429 Too Many Requests` with a `Retry-After` header.

---

## How It Differs from Other Services

| Aspect | Other Services | API Gateway |
|---|---|---|
| Database | MongoDB / PostgreSQL | None |
| Business logic | Yes | None — pure routing |
| Kafka | Producer / Consumer | None |
| External calls | LLM APIs | Downstream microservices |
| Authentication | Trust gateway | Validates JWT |
| Rate limiting | None | Per-route limits |

---

## Unit Tests — What's Covered

### `test_gateway.py` — 21 tests

| Area | Tests |
|---|---|
| Health check | Returns UP with service info and auth status |
| Product routes | List, by ID, search with query params, create (POST) |
| Order routes | List, create, by ID |
| Inventory routes | List, check stock with query params, reduce (PATCH) |
| AI routes | Chat, recommendations, suggest |
| Error handling | 503 service unavailable, 504 timeout, 404 forwarded, 400 forwarded |
| Auth disabled | No header works, auth header stripped before forwarding |
| Forwarding | Query params forwarded, request body forwarded |

### `test_auth.py` — 9 tests

| Area | Tests |
|---|---|
| Auth disabled | Returns dev user payload, ignores auth header |
| Missing header | No header → 401, no Bearer prefix → 401, empty Bearer → 401 |
| Token validation | Valid token → returns payload, expired → 403, bad audience → 401, bad issuer → 401 |

---

## Environment Setup

### Prerequisites
- Homebrew Python 3.12
- Docker Desktop (for Keycloak, when enabling auth)
- All downstream services running

### Running Locally

```bash
cd api-gateway
/opt/homebrew/bin/python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

touch app/__init__.py app/auth/__init__.py app/middleware/__init__.py
touch tests/__init__.py tests/unit/__init__.py

python -m uvicorn app.main:app --port 9000 --loop asyncio
```

### Running Tests

```bash
cd api-gateway
source venv/bin/activate
pytest -v
```

### Environment Variables (`.env`)

```
APP_NAME=api-gateway
APP_PORT=9000

# Downstream services
PRODUCT_SERVICE_URL=http://localhost:8001
ORDER_SERVICE_URL=http://localhost:8002
INVENTORY_SERVICE_URL=http://localhost:8003
AI_SERVICE_URL=http://localhost:8005

# Keycloak
KEYCLOAK_URL=http://localhost:8081
KEYCLOAK_REALM=microservices
KEYCLOAK_CLIENT_ID=api-gateway

# Rate limiting
RATE_LIMIT_DEFAULT=60/minute
RATE_LIMIT_AI=15/minute

# Set to true when Keycloak is configured
AUTH_ENABLED=false
```

---

## Keycloak Setup (When Enabling Auth)

### 1. Access Keycloak Admin Console
```
http://localhost:8081
Username: admin
Password: admin
```

### 2. Create Realm
- Click "Create Realm"
- Name: `microservices`
- Save

### 3. Create Client
- Go to Clients → Create Client
- Client ID: `api-gateway`
- Client Protocol: `openid-connect`
- Access Type: `public`
- Valid Redirect URIs: `http://localhost:9000/*`
- Save

### 4. Create Test User
- Go to Users → Add User
- Username: `testuser`
- Email: `test@example.com`
- Save → Credentials tab → Set password

### 5. Get a Token
```bash
curl -X POST http://localhost:8081/realms/microservices/protocol/openid-connect/token \
  -d "client_id=api-gateway" \
  -d "username=testuser" \
  -d "password=testpass" \
  -d "grant_type=password"
```

### 6. Enable Auth
Set `AUTH_ENABLED=true` in `.env` and restart the gateway.

### 7. Use the Token
```bash
curl http://localhost:9000/api/products \
  -H "Authorization: Bearer <token>"
```

---

## Relationship with Other Services

```
                    ┌──────────────────────┐
                    │    API Gateway        │
                    │    Port: 9000         │
                    │                       │
                    │  ┌─ JWT Validation    │
                    │  ├─ Rate Limiting     │
                    │  └─ Request Proxy     │
                    └──┬──┬──┬──┬──────────┘
                       │  │  │  │
          ┌────────────┘  │  │  └──────────────┐
          ▼               ▼  ▼                  ▼
   Product Service  Order Service  Inventory  AI Service
      :8001           :8002        :8003       :8005
```

The API Gateway depends on all downstream services being available. If a service is down, the gateway returns 503 for that service's routes — other services remain accessible.

---

## Key Lessons Learned

**Feature flags eliminate development friction.** `AUTH_ENABLED=false` means the full system works without configuring Keycloak. The same pattern (`EMAIL_ENABLED`, `AUTH_ENABLED`) is used consistently across services.

**A shared httpx client with connection pooling is essential.** Creating a new HTTP connection per request adds latency and exhausts file descriptors under load. The gateway's shared client maintains persistent connections to all downstream services.

**Strip auth headers before forwarding.** Downstream services should not receive or validate JWTs — the gateway is the single point of authentication. Forwarding the Authorization header creates unnecessary coupling.

**AI routes need stricter rate limits.** LLM calls take 1-5 seconds and have their own provider rate limits. The gateway's 15/minute limit for AI routes prevents a single client from exhausting the LLM quota.

**Downstream errors should be forwarded, not swallowed.** When a service returns 404 or 400, the gateway passes it through. Only infrastructure failures (connection refused, timeout) get translated to 503/504.
