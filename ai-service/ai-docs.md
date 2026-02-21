# AI Service — Technical Documentation

## Overview

The AI Service is the fifth microservice in the FastAPI Microservices project. It provides AI-powered features for the e-commerce platform: a shopping assistant chatbot, product recommendations, natural language product search, and personalized email generation. It fetches real product data from the Product Service and uses a provider-agnostic LLM abstraction layer that supports Google Gemini, Groq (Llama 3.3 70B), and Ollama (local).

---

## Tech Stack Decisions

### Provider-Agnostic LLM Design
The AI Service uses an abstract `LLMClient` base class with concrete implementations for each provider. To switch from Groq to Gemini or Ollama, change one line in `.env` — no code changes required. This was a deliberate architecture decision to avoid vendor lock-in and to make the service resilient to provider outages or rate limit issues.

### Groq over Google Gemini (Primary Provider)
Groq was selected as the primary provider because it offers a generous free tier (30 RPM on Llama 3.3 70B) with extremely fast inference. Google Gemini's free tier proved too restrictive during development — rapid Kafka event processing exhausted the daily quota quickly. Groq's rate limits are more forgiving for burst workloads.

### Llama 3.3 70B via Groq
Llama 3.3 70B is Meta's open-source large language model. It runs on Groq's cloud infrastructure — the model itself is free and open-source, Groq provides the compute. The model is capable enough for structured JSON generation (recommendations, search results) and natural conversation (chatbot).

### httpx for LLM API Calls (No SDKs)
All LLM providers are called via `httpx` REST calls rather than provider-specific SDKs (`google-generativeai`, `openai`, `groq`). This keeps dependencies minimal, maintains consistency with the rest of the project (which uses `httpx` for inter-service calls), and makes the provider abstraction cleaner — each client is just an HTTP wrapper.

### Real Product Data from Product Service
The AI Service calls the Product Service (`GET /api/products`) to fetch the real catalog before every LLM call. This means recommendations, search results, and chatbot responses reference actual products in the system rather than hallucinated ones. The product data is formatted into a text block and injected into the LLM's system prompt.

### Kafka Consumer + Producer
The AI Service acts as both a Kafka consumer and producer. It consumes `order-placed` events, generates personalized email content via the LLM, and publishes the result to `ai-notification-ready` for the Notification Service to send. This creates a fully asynchronous AI personalization pipeline.

### Non-blocking Kafka with Rate Limiting
A 5-second delay between Kafka message processing prevents LLM rate limit exhaustion when multiple orders arrive simultaneously. The Kafka consumer catches all exceptions per message — a failed personalization does not block subsequent events.

---

## Project Structure

```
ai-service/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app, lifespan, Kafka consumer task
│   ├── config.py                    # Settings from .env (all providers + Kafka)
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract LLMClient interface
│   │   ├── gemini_client.py         # Google Gemini implementation
│   │   ├── groq_client.py          # Groq / Llama 3.3 70B implementation
│   │   ├── ollama_client.py        # Ollama local implementation
│   │   └── factory.py              # Returns configured client based on LLM_PROVIDER
│   ├── clients/
│   │   ├── __init__.py
│   │   └── product_client.py        # httpx client to fetch products from Product Service
│   ├── routes/
│   │   ├── __init__.py
│   │   └── ai_routes.py             # 3 REST endpoints (chat, recommendations, suggest)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chatbot.py               # Shopping assistant with conversation history
│   │   ├── recommendation.py        # Product recommendations from real catalog
│   │   ├── suggestion.py            # Natural language product search
│   │   └── notification_ai.py       # Personalized email generation for orders
│   └── kafka/
│       ├── __init__.py
│       ├── consumer.py              # Consumes order-placed events
│       └── producer.py              # Publishes ai-notification-ready events
├── tests/
│   ├── __init__.py
│   └── unit/
│       ├── __init__.py
│       ├── test_llm_clients.py      # 14 tests — all 3 LLM providers
│       ├── test_ai_services.py      # 17 tests — chatbot, recommendations, suggestion, notification
│       ├── test_product_client.py   # 10 tests — product fetching and formatting
│       └── test_kafka.py            # 3 tests — order-placed handler
├── pytest.ini
├── Dockerfile
├── requirements.txt
└── .env
```

---

## LLM Provider Architecture

```
                    ┌──────────────────┐
                    │   LLMClient      │  ← Abstract base class
                    │   (base.py)      │
                    │                  │
                    │  + generate()    │  ← Single method interface
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ GeminiClient │ │  GroqClient  │ │ OllamaClient │
   │              │ │              │ │              │
   │ Google API   │ │ Groq API     │ │ localhost    │
   │ Free tier    │ │ Free tier    │ │ No API key   │
   │ 15 RPM       │ │ 30 RPM       │ │ Unlimited    │
   └──────────────┘ └──────────────┘ └──────────────┘

   factory.py reads LLM_PROVIDER from .env
   and returns the correct client instance
```

### How to Switch Providers

Change one line in `.env`:
```
LLM_PROVIDER=groq      # Groq / Llama 3.3 70B (current)
LLM_PROVIDER=gemini    # Google Gemini
LLM_PROVIDER=ollama    # Ollama (local, no API key)
```

### Adding a New Provider

1. Create `app/llm/new_provider_client.py` extending `LLMClient`
2. Implement the `generate(prompt, system_prompt)` method
3. Add the provider's settings to `config.py` and `.env`
4. Register it in `factory.py`

---

## AI Features

### 1. Shopping Assistant Chatbot
| | |
|---|---|
| **Endpoint** | `POST /api/ai/chat` |
| **Trigger** | REST call |
| **Input** | Message + optional conversation history |
| **Output** | AI reply referencing real products |
| **Context** | Fetches full product catalog from Product Service |

```json
// Request
{
  "message": "I'm looking for a gift under $100",
  "history": [
    { "role": "user", "content": "Hi" },
    { "role": "assistant", "content": "Hello! How can I help?" }
  ]
}

// Response
{ "reply": "We don't have products under $100 currently..." }
```

### 2. Product Recommendations
| | |
|---|---|
| **Endpoint** | `GET /api/ai/recommendations?product_name=iPhone&category=Electronics` |
| **Trigger** | REST call |
| **Input** | Product name and/or category |
| **Output** | JSON with 5 recommended products from real catalog |

### 3. Smart Search (Natural Language)
| | |
|---|---|
| **Endpoint** | `POST /api/ai/suggest` |
| **Trigger** | REST call |
| **Input** | Natural language query |
| **Output** | Matching products, search tags, and category |

```json
// Request
{ "query": "something warm for winter under $50" }

// Response
{ "result": "{\"matches\": [...], \"search_tags\": [\"winter\"], ...}" }
```

### 4. Notification Personalization
| | |
|---|---|
| **Trigger** | Kafka event (`order-placed`) |
| **Input** | Order details from Kafka |
| **Output** | Personalized email subject + HTML body |
| **Publishes to** | `ai-notification-ready` Kafka topic |

---

## Kafka Event Flow

```
Order Service
      │
      │ publishes order-placed event
      ▼
┌─────────────────────────────────────────┐
│              AI Service                 │
│                                         │
│  1. Consume order-placed event          │
│  2. Fetch products from Product Service │
│  3. Build prompt with order details     │
│  4. Call LLM for personalized email     │
│  5. Parse JSON response                 │
│  6. Publish to ai-notification-ready    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
         Notification Service
         (sends the personalized email)
```

### Topics

| Topic | Role | Purpose |
|---|---|---|
| `order-placed` | Consumer | Receives new order events |
| `ai-notification-ready` | Producer | Sends personalized email content to Notification Service |

### Event Schema — `ai-notification-ready`
```json
{
  "order_number": "ORD-20260221-38F5F24F",
  "customer_email": "yash@example.com",
  "customer_name": "Yash Vyas",
  "subject": "Thanks for your order!",
  "body_html": "<html>...personalized email...</html>"
}
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/chat` | Shopping assistant chatbot |
| `GET` | `/api/ai/recommendations` | Product recommendations |
| `POST` | `/api/ai/suggest` | Natural language product search |
| `GET` | `/health` | Health check (includes LLM provider info) |

---

## How It Differs from Other Services

| Aspect | Other Services | AI Service |
|---|---|---|
| Database | MongoDB / PostgreSQL | None (stateless) |
| External API | None | LLM provider (Groq/Gemini/Ollama) |
| Inter-service calls | Order → Inventory | AI → Product Service |
| Kafka role | Producer or Consumer | Both Consumer and Producer |
| Response time | Milliseconds | 1-5 seconds (LLM latency) |

---

## Resilience Patterns

### Retry with Exponential Backoff (Gemini & Groq)
```
Attempt 1 → 429 → wait 2s
Attempt 2 → 429 → wait 4s
Attempt 3 → 429 → wait 8s
After 3 failures → return fallback message (no crash)
```

### Graceful Fallback on All Errors
Every LLM client returns a user-friendly fallback message instead of raising exceptions. This means:
- 429 rate limits → "AI service is temporarily busy"
- 500 server errors → same fallback
- Connection refused (Ollama not running) → "Is Ollama running?"
- Timeout → "Request timed out"
- Malformed JSON from LLM → default email subject/body

### Non-critical Kafka
Kafka publish failure does not crash the consumer. If `ai-notification-ready` fails to publish, the error is logged and the consumer continues processing the next event.

### Product Service Unavailable
If the Product Service is down, the AI Service continues with an empty catalog context. The LLM will still respond, just without product-specific information.

### Kafka Message Throttling
A 5-second delay between Kafka messages prevents LLM rate limit exhaustion from burst order events.

---

## Unit Tests — What's Covered

### `test_llm_clients.py` — 14 tests

| Area | Tests |
|---|---|
| Gemini | Success, system prompt, 500 error fallback, 429 retry + fallback, malformed response |
| Groq | Success, system prompt, 500 error fallback, 429 retry + fallback |
| Ollama | Success, 500 error fallback, connection refused, timeout |

### `test_ai_services.py` — 17 tests

| Area | Tests |
|---|---|
| Chatbot | Returns LLM response, includes product context, empty catalog, passes history, no history |
| Recommendations | Returns response, includes product name in prompt, includes category, empty catalog |
| Suggestion | Returns response, includes query in prompt, empty catalog |
| Notification AI | Returns subject + body, includes customer in prompt, malformed response, markdown-fenced JSON, empty catalog |

### `test_product_client.py` — 10 tests

| Area | Tests |
|---|---|
| get_all_products | List response, dict with products key, connection error returns empty |
| search_products | List response, error returns empty |
| format_products | Empty list, single product, no tags, with description, 50-product limit, missing fields, product_name key |

### `test_kafka.py` — 3 tests

| Area | Tests |
|---|---|
| _handle_order_placed | Calls personalize, publishes correct notification event, preserves customer info |

---

## Environment Setup

### Prerequisites
- Homebrew Python 3.12
- Docker Desktop with Kafka container running
- Groq API key (free at https://console.groq.com/keys)
- Product Service running on port 8001 (for real catalog data)

### Running Locally

```bash
cd ai-service
/opt/homebrew/bin/python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create __init__.py files
touch app/__init__.py app/llm/__init__.py app/clients/__init__.py
touch app/routes/__init__.py app/services/__init__.py app/kafka/__init__.py
touch tests/__init__.py tests/unit/__init__.py

python -m uvicorn app.main:app --port 8005 --loop asyncio
```

### Running Tests

```bash
cd ai-service
source venv/bin/activate
pytest -v
```

### Environment Variables (`.env`)

```
APP_NAME=ai-service
APP_PORT=8005

# LLM Provider — change to swap (gemini, groq, ollama)
LLM_PROVIDER=groq

# Google Gemini
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash

# OpenAI (future)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o

# Groq
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Product Service
PRODUCT_SERVICE_URL=http://localhost:8001

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_GROUP_ID=ai-service-group
KAFKA_ORDER_PLACED_TOPIC=order-placed
KAFKA_AI_NOTIFICATION_TOPIC=ai-notification-ready
```

---

## Relationship with Other Services

```
Product Service ◄── AI Service (fetches real catalog via REST)
                         │
                         │ consumes order-placed (Kafka)
                         │ publishes ai-notification-ready (Kafka)
                         ▼
                  Notification Service (sends personalized email)
```

The AI Service depends on:
- **Product Service** (synchronous REST) — for real catalog data in LLM context
- **Kafka** (asynchronous) — for order events and notification publishing
- **LLM Provider** (external API) — Groq, Gemini, or Ollama

If the Product Service is down, AI features still work with an empty catalog. If Kafka is down, REST endpoints still work. If the LLM provider is down, all features return graceful fallback messages.

---

## Issues Encountered and Fixes

### Issue 1 — Gemini Daily Rate Limit Exhausted

**What happened:**
The Kafka consumer processed 6 old `order-placed` events rapidly on first startup, each triggering a Gemini API call. Combined with retry attempts (3 per failure), this exhausted the free tier daily quota within minutes.

**Root cause:**
Kafka's `auto_offset_reset=earliest` caused the consumer to replay all historical messages. Each message triggered an LLM call, and each 429 retry fired additional calls, creating a cascading rate limit problem.

**Fix:**
Three changes: (1) Reset the consumer group offset to latest using `kafka-consumer-groups --reset-offsets --to-latest`. (2) Added retry with exponential backoff (2s, 4s, 8s) in the Gemini client. (3) Added a 5-second delay between Kafka messages to prevent burst requests. Ultimately switched to Groq which has a more generous free tier.

### Issue 2 — Product Service Response Format Mismatch

**What happened:**
The AI Service crashed with `KeyError: slice(None, 50, None)` when trying to format products for LLM context.

**Root cause:**
The Product Service returns `{"products": [...], "total": 2, "page": 1}` (a dict), but `format_products_for_context` expected a list and tried `products[:50]` on a dict.

**Fix:**
Updated `product_client.py` to handle both list and dict response formats. It checks for common wrapper keys (`products`, `data`, `items`, `results`) and extracts the list automatically.

### Issue 3 — Missing `groq_client.py` and `ollama_client.py`

**What happened:**
The service crashed on startup with `ModuleNotFoundError: No module named 'app.llm.groq_client'`.

**Root cause:**
The files were generated as artifacts but not yet created in the filesystem. The factory imported them but they didn't exist on disk.

**Fix:**
Created both files manually in `app/llm/`. Lesson: always verify files exist with `ls app/llm/` after generating artifacts.

### Issue 4 — `config.py` Missing Ollama Settings

**What happened:**
Ollama unit tests failed with `AttributeError: 'Settings' object has no attribute 'OLLAMA_MODEL'`.

**Root cause:**
The `OLLAMA_BASE_URL` and `OLLAMA_MODEL` fields were not declared in the `Settings` class in `config.py`. Pydantic-settings only reads `.env` values that have corresponding field declarations.

**Fix:**
Added `OLLAMA_BASE_URL` and `OLLAMA_MODEL` fields to the Settings class in `config.py` and corresponding entries in `.env`.

### Issue 5 — Pydantic Rejecting Extra `.env` Fields

**What happened:**
After accidentally deleting Groq fields from `config.py`, all tests failed with `Extra inputs are not permitted` for `groq_api_key` and `groq_model`.

**Root cause:**
The `.env` file contained `GROQ_API_KEY` and `GROQ_MODEL`, but `config.py` no longer declared these fields. Pydantic's default behavior rejects undeclared fields.

**Fix:**
Restored the Groq fields in `config.py`. Every field in `.env` must have a corresponding declaration in the `Settings` class.

---

## Key Lessons Learned

**Provider-agnostic design pays off immediately.** Switching from Gemini to Groq took zero code changes — just a `.env` update. When Gemini's rate limits became a problem, the switch was instant.

**LLM rate limits require careful handling in event-driven systems.** Kafka can deliver many events simultaneously. Without throttling and retry logic, a burst of orders can exhaust API quotas in seconds.

**Always handle LLM response parsing defensively.** LLMs don't always return valid JSON, even when instructed to. The notification personalization service strips markdown fences and falls back to defaults on parse failure.

**Real product data makes AI features meaningful.** Fetching from the Product Service means the chatbot, recommendations, and search results reference actual inventory rather than hallucinated products.

**Every `.env` field needs a corresponding `config.py` declaration.** Pydantic-settings rejects undeclared fields by default. The `.env` file provides values; `config.py` provides the schema.

**Kafka consumer offsets must be managed when adding new consumers.** Historical events replay on first connection with `auto_offset_reset=earliest`. Use `--reset-offsets --to-latest` to skip old events when the consumer first joins.
