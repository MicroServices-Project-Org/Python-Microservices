🏗️ FastAPI Microservices — E-Commerce Platform with AI
A production-grade microservices architecture built with FastAPI, Kafka, PostgreSQL, MongoDB, and OpenAI — designed to demonstrate real-world patterns including event-driven communication, inter-service REST calls, resilience patterns, and AI integration.

📐 System Architecture
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
    MongoDB         PostgreSQL    PostgreSQL       OpenAI API
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
                            └─────────────────┘

  ┌─────────────────────────────────────────────────┐
  │              Keycloak (Port: 8081)              │
  │         OAuth2 / JWT Identity Provider          │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │           Observability Stack                   │
  │  Prometheus → Grafana │ Loki (logs) │ Tempo     │
  └─────────────────────────────────────────────────┘

🧩 Services Overview
ServiceResponsibilityDatabasePortStatusProduct ServiceCRUD for product catalogMongoDB8001✅ CompleteOrder ServicePlace & manage orders, Kafka producerPostgreSQL8002✅ CompleteInventory ServiceStock management, stock verificationPostgreSQL8003✅ CompleteNotification ServiceEmail notifications via Kafka eventsNone (stateless)8004✅ CompleteAI ServiceRecommendations, chatbot, smart searchNone (stateless)8005🔲 PlannedAPI GatewayRouting, auth, rate limitingNone9000🔲 Planned

🛠️ Tech Stack
CategoryTechnologyFrameworkFastAPI (async-native)LanguagePython 3.12DatabasesPostgreSQL 16, MongoDB 7.0Message BrokerApache Kafka (Confluent 7.6.0)ORMSQLAlchemy (async) for PostgreSQL, Motor (async) for MongoDBValidationPydantic v2HTTP Clienthttpx (async)Resiliencetenacity (retry), pybreaker (circuit breaker)IdentityKeycloak 24.0 (OAuth2 / JWT)ObservabilityPrometheus, Grafana, Loki, TempoContainerizationDocker, Docker ComposeCI/CDGitHub ActionsTestingpytest, pytest-asyncio, unittest.mock

📦 Project Structure
Python-Microservices/
│
├── product-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py              # Motor async MongoDB client
│   │   ├── schemas/
│   │   │   └── product.py           # Pydantic request/response models
│   │   ├── routes/
│   │   │   └── product_routes.py
│   │   └── services/
│   │       └── product_service.py
│   ├── tests/
│   │   └── unit/
│   │       └── test_product_service.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── order-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py              # SQLAlchemy async + PostgreSQL
│   │   ├── models/
│   │   │   └── order.py             # SQLAlchemy ORM (orders + order_items)
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
│   │   └── unit/
│   │       └── test_order_service.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── inventory-service/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py              # SQLAlchemy async + PostgreSQL
│   │   ├── models/
│   │   │   └── inventory.py         # SQLAlchemy ORM
│   │   ├── schemas/
│   │   │   └── inventory.py
│   │   ├── routes/
│   │   │   └── inventory_routes.py
│   │   └── services/
│   │       └── inventory_service.py
│   ├── tests/
│   │   └── unit/
│   │       └── test_inventory_service.py
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
│   │   └── unit/
│   │       ├── test_email_service.py
│   │       └── test_kafka_consumer.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker/
│   ├── postgres/
│   │   └── init-multiple-dbs.sh     # Creates order_db + inventory_db
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

🔗 Inter-Service Communication
Synchronous (REST/HTTP)
Order Service ──► Inventory Service
  GET  /api/inventory/{product_id}/check?quantity=N   (verify stock)
  PATCH /api/inventory/{product_id}/reduce            (reduce stock)
Asynchronous (Kafka)
Order Service ──► [order-placed]          ──► Notification Service (confirmation email)
Order Service ──► [order-placed]          ──► AI Service (personalize email)
Order Service ──► [order-cancelled]       ──► Notification Service (cancellation email)
Inventory Svc ──► [inventory-low]         ──► Notification Service (low stock alert)
AI Service    ──► [ai-notification-ready] ──► Notification Service (personalized email)
Kafka Topics
TopicProducerConsumersPurposeorder-placedOrder ServiceNotification, AI ServiceNew order createdorder-cancelledOrder ServiceNotification ServiceOrder cancelledinventory-lowInventory ServiceNotification ServiceStock alertai-notification-readyAI ServiceNotification ServicePersonalized email ready

🗄️ Database Schemas
Product Service — MongoDB
jsonCollection: products
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
Order Service — PostgreSQL
Table: orders
  id (UUID, PK) | order_number | customer_name | customer_email
  total_amount   | status (ENUM) | created_at   | updated_at

  Status: PENDING → CONFIRMED → SHIPPED → DELIVERED → CANCELLED

Table: order_items
  id (UUID, PK) | order_id (FK) | product_id | product_name
  quantity       | unit_price    | total_price
Inventory Service — PostgreSQL
Table: inventory
  id (UUID, PK)  | product_id (unique) | product_name
  quantity        | reserved_qty        | created_at | updated_at

  Computed: available_qty = quantity - reserved_qty

🔌 API Endpoints
Product Service (Port 8001)
MethodEndpointDescriptionPOST/api/productsCreate a new productGET/api/productsList all productsGET/api/products/search?q=Search by name, category, or tagsGET/api/products/{id}Get product by IDPUT/api/products/{id}Update productDELETE/api/products/{id}Delete product
Order Service (Port 8002)
MethodEndpointDescriptionPOST/api/ordersPlace a new orderGET/api/ordersGet all ordersGET/api/orders/{order_id}Get order by IDGET/api/orders/user/{email}Get orders by customer emailPATCH/api/orders/{order_id}/statusUpdate order statusPATCH/api/orders/{order_id}/cancelCancel an order
Inventory Service (Port 8003)
MethodEndpointDescriptionPOST/api/inventoryAdd inventory itemGET/api/inventoryList all inventoryGET/api/inventory/{product_id}Get stock for productGET/api/inventory/{product_id}/check?quantity=NCheck stock availabilityPATCH/api/inventory/{product_id}/reduceReduce stockPATCH/api/inventory/{product_id}/restockRestock itemPUT/api/inventory/{product_id}Update inventoryDELETE/api/inventory/{product_id}Delete inventory item
Notification Service (Port 8004)
MethodEndpointDescriptionGET/healthHealth check

The Notification Service has no REST API. It consumes Kafka events and sends emails.


🔄 Order Flow (End-to-End)
1. Client → POST /api/orders
2. Order Service → GET /api/inventory/{id}/check?quantity=N  (verify stock)
3. If in stock → save order to PostgreSQL
4. Order Service → PATCH /api/inventory/{id}/reduce          (reduce stock)
5. Order Service → publish 'order-placed' event to Kafka
6. Notification Service → consumes event → logs/sends confirmation email
7. Return 201 Created to client

🧪 Testing
Each service has unit tests using pytest with unittest.mock for mocking external dependencies.
ServiceTest FileTestsWhat's CoveredProduct Servicetest_product_service.py—CRUD operations, search, validationOrder Servicetest_order_service.py15Order creation, stock checks, cancellation, Kafka publishingInventory Servicetest_inventory_service.py20CRUD, stock check, reduce, restock, edge casesNotification Servicetest_email_service.py20Email templates, SMTP send/disabled modesNotification Servicetest_kafka_consumer.py14Message routing, all 4 topic handlers
Running Tests
bashcd <service-directory>
source venv/bin/activate
pytest -v

🐳 Infrastructure (Docker Compose)
All infrastructure runs via Docker Compose:
ServicePortPurposeMongoDB27017Product Service databasePostgreSQL5433Order + Inventory databasesKafka9092Event streamingZookeeper2181Kafka coordinationKafka UI8090Visual Kafka managementKeycloak8081OAuth2 / JWT identity providerPrometheus9090Metrics collectionGrafana3000DashboardsLoki3100Log aggregationTempo3200Distributed tracing
Starting Infrastructure
bashcd Python-Microservices
docker-compose up -d
Verifying Services
bash# Check all containers are healthy
docker ps --format "table {{.Names}}\t{{.Status}}"

# Check Kafka topics
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092

# Open Kafka UI
open http://localhost:8090
Stopping Everything
bashdocker-compose down       # stop containers, keep data
docker-compose down -v    # stop containers, delete all data

🚀 Running the Application
Prerequisites

macOS with Homebrew
Python 3.12 (via Homebrew, not Anaconda)
Docker Desktop

Step 1 — Start Infrastructure
bashcd Python-Microservices
docker-compose up -d
Step 2 — Start Services (each in a separate terminal)
Product Service:
bashcd product-service
source venv/bin/activate
python -m uvicorn app.main:app --port 8001 --loop asyncio
Inventory Service:
bashcd inventory-service
source venv/bin/activate
python -m uvicorn app.main:app --port 8003 --loop asyncio
Order Service:
bashcd order-service
source venv/bin/activate
python -m uvicorn app.main:app --port 8002 --loop asyncio
Notification Service:
bashcd notification-service
source venv/bin/activate
python -m uvicorn app.main:app --port 8004 --loop asyncio
Step 3 — Test the Flow
bash# 1. Add a product to inventory
curl -X POST http://localhost:8003/api/inventory \
  -H "Content-Type: application/json" \
  -d '{"product_id": "prod-001", "product_name": "iPhone 15 Pro", "quantity": 100}'

# 2. Place an order
curl -X POST http://localhost:8002/api/orders \
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

# 3. Check Notification Service terminal for email log output

📝 Service Documentation
Each service has detailed technical documentation covering architecture decisions, issues encountered, and lessons learned:
ServiceDocumentationProduct Serviceproduct-service/product-service-docs.mdOrder Serviceorder-service/order-docs.mdInventory Serviceinventory-service/inventory-docs.mdNotification Servicenotification-service/notification-docs.md

🐛 Notable Issues & Fixes
IssueRoot CauseFixAnaconda interfering with async event loopvenv inherited Anaconda's sys.path, Motor fell back to sync PyMongoRemoved Anaconda, created venv with Homebrew PythonMongoDB auth failing from host to DockerSCRAM auth broken over Docker TCP bridge on MacDisabled auth for local devmotor + pymongo version incompatibilityMotor 3.4.0 relied on removed PyMongo internalsPinned motor==3.5.1 + pymongo==4.8.0PostgreSQL init script not runningData volume already initialized from previous rundocker-compose down -v to reset volumesPort conflicts on Mac (8080, 5432)Java process on 8080, local PostgreSQL on 5432Remapped to 8081, 5433 in docker-composeSQLAlchemy async missing greenletNot auto-installed as SQLAlchemy dependencyAdded greenlet to requirements.txtModuleNotFoundError: No module named 'app'Missing __init__.py files + shared venvCreated __init__.py files, dedicated venv per service

🗺️ Build Roadmap
Phase 1 ✅ Infrastructure
  └── Docker Compose (Kafka, PostgreSQL, MongoDB, Keycloak, Observability)

Phase 2 ✅ Core Services
  ├── Product Service (MongoDB, Motor async)
  ├── Inventory Service (PostgreSQL, SQLAlchemy async)
  └── Order Service (PostgreSQL, httpx, aiokafka)

Phase 3 ✅ Async Layer
  └── Notification Service (Kafka consumer, Gmail SMTP)

Phase 4 ✅ AI Layer
  └── AI Service (Groq/Llama 3.3 70B, Kafka consumer + producer, REST API)

Phase 5 🔲 Gateway & Security
  └── API Gateway (routing, JWT validation, rate limiting)

Phase 6 🔲 Resilience
  ├── Circuit Breaker (pybreaker)
  ├── Retry + Backoff (tenacity)
  ├── Timeouts (httpx)
  └── Rate Limiting (slowapi)

Phase 7 🔲 Observability
  └── Prometheus, Grafana, Loki, Tempo wiring

Phase 8 🔲 CI/CD
  └── GitHub Actions (lint → test → build → deploy)

📄 License
This project is built for learning and portfolio purposes.

👤 Author
Yash Vyas