# Search Service — Technical Documentation

## Overview

The Search Service is the seventh microservice and the first Java service in the project. It provides full-text product search, autocomplete suggestions, and faceted filtering powered by Elasticsearch. It stays in sync with the Product Service via Kafka events — when a product is created, updated, or deleted in MongoDB, the Search Service reindexes it in Elasticsearch.

**Polyglot architecture:** This service is built with Java 21 + Spring Boot 3.3 while the rest of the platform uses Python + FastAPI. Microservices communicate via HTTP and Kafka, which are language-agnostic — demonstrating that each service can use the best tool for the job.

---

## Tech Stack Decisions

### Java + Spring Boot over Python
Elasticsearch's most mature client libraries are Java-native. Spring Data Elasticsearch provides repository abstraction, automatic index creation, and query DSL integration out of the box. Java's strong typing also makes Elasticsearch document mapping more explicit and less error-prone.

### Spring Data Elasticsearch over Raw REST Client
Spring Data Elasticsearch provides a repository pattern (`ElasticsearchRepository`) that handles CRUD operations automatically, plus `ElasticsearchOperations` for custom queries like full-text search and criteria-based filtering. This eliminates writing raw Elasticsearch JSON queries.

### Elasticsearch over MongoDB Text Search
The Product Service already has basic text search via MongoDB's `$text` operator. Elasticsearch provides significantly better search capabilities: fuzzy matching, relevance scoring, autocomplete, faceted filtering, and multi-field search across name, description, tags, and category simultaneously.

### Kafka Consumer for Real-Time Sync
Products are the source of truth in MongoDB (Product Service). Elasticsearch is a read-optimized copy. The Search Service consumes `product-updated` Kafka events to keep the index in sync. If Elasticsearch goes down, the Product Service still works — search is just temporarily unavailable.

### No Lombok
Lombok was initially planned but removed due to annotation processing issues with Java 21 + Maven. All getters, setters, constructors, and builders are written explicitly. This eliminates a dependency and makes the code fully transparent.

---

## Project Structure

```
search-service/
├── src/main/java/com/ecommerce/search/
│   ├── SearchApplication.java              # Spring Boot entry point
│   ├── controller/
│   │   └── SearchController.java           # REST endpoints
│   ├── model/
│   │   └── Product.java                    # Elasticsearch document
│   ├── repository/
│   │   └── ProductSearchRepository.java    # Spring Data ES repository
│   ├── service/
│   │   └── SearchService.java              # Business logic
│   └── kafka/
│       └── ProductEventConsumer.java       # Consumes product-updated topic
├── src/main/resources/
│   └── application.yml                     # Configuration
├── src/test/java/com/ecommerce/search/
│   └── service/
│       └── SearchServiceTest.java          # 15 JUnit 5 + Mockito tests
├── pom.xml                                 # Maven build
└── Dockerfile
```

---

## Elasticsearch Index

```json
Index: products
{
  "name": "iPhone 15 Pro",          // Text — full-text searchable
  "description": "Latest Apple...", // Text — full-text searchable
  "price": 999.99,                  // Double — range filtering
  "category": "Electronics",        // Keyword — exact match filtering
  "tags": ["smartphone", "apple"],  // Keyword array — searchable
  "imageUrl": "https://...",        // Text
  "stockQuantity": 100,             // Integer
  "suggest": {                      // Completion — autocomplete
    "input": ["iPhone", "iPhone 15", "iPhone 15 Pro"]
  }
}
```

### Autocomplete Suggestions
When a product is indexed, the `suggest` field is automatically populated with progressive prefixes of the product name. For "iPhone 15 Pro", the inputs are: "iPhone", "iPhone 15", "iPhone 15 Pro". This enables type-ahead search.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/search?q=iphone` | Full-text search across name, description, tags, category |
| `GET` | `/api/search/autocomplete?q=iPh` | Autocomplete suggestions based on product names |
| `GET` | `/api/search/filter?category=Electronics&minPrice=500&maxPrice=1500` | Faceted filtering by category and price range |
| `GET` | `/api/search/health` | Health check |

### Response Formats

**Full-text search:**
```json
{
  "query": "iphone",
  "total": 1,
  "results": [
    {
      "id": "prod-001",
      "name": "iPhone 15 Pro",
      "description": "Latest Apple smartphone",
      "price": 999.99,
      "category": "Electronics",
      "tags": ["smartphone", "apple", "5g"]
    }
  ]
}
```

**Autocomplete:**
```json
{
  "prefix": "iPh",
  "suggestions": ["iPhone 15 Pro"]
}
```

**Faceted filter:**
```json
{
  "filters": {
    "category": "Electronics",
    "minPrice": 500.0,
    "maxPrice": 1500.0
  },
  "total": 1,
  "results": [...]
}
```

---

## Kafka Integration

### Topic: `product-updated`

The Search Service consumes events from the `product-updated` topic to keep Elasticsearch in sync with MongoDB.

```
Product Service (Python/MongoDB)
      │
      │ publishes product-updated event to Kafka
      ▼
Search Service (Java/Elasticsearch)
      │
      │ consumes event → indexes/deletes in Elasticsearch
      ▼
Client searches via REST API → Elasticsearch returns results
```

### Event Schema

**Product Created/Updated:**
```json
{
  "_id": "prod-001",
  "name": "iPhone 15 Pro",
  "description": "Latest Apple smartphone",
  "price": 999.99,
  "category": "Electronics",
  "tags": ["smartphone", "apple", "5g"],
  "stock_quantity": 100
}
```

**Product Deleted:**
```json
{
  "event_type": "DELETED",
  "product_id": "prod-001"
}
```

---

## How It Differs from Python Services

| Aspect | Python Services | Search Service |
|---|---|---|
| Language | Python 3.12 | Java 21 |
| Framework | FastAPI (async) | Spring Boot 3.3 (servlet) |
| Build tool | pip + requirements.txt | Maven + pom.xml |
| Database | MongoDB / PostgreSQL | Elasticsearch |
| ORM | SQLAlchemy / Motor | Spring Data Elasticsearch |
| Testing | pytest + unittest.mock | JUnit 5 + Mockito |
| Container | `python:3.12-slim` | `eclipse-temurin:21-jre-alpine` |
| Config | `.env` + pydantic-settings | `application.yml` |

---

## Unit Tests — What's Covered

### `SearchServiceTest.java` — 15 tests

| Area | Tests |
|---|---|
| Full-text search | Returns matching products, empty for no match, multiple results |
| Autocomplete | Returns suggestions, empty for no match, distinct names only |
| Faceted filter | By category, by price range, by both, no filters returns all |
| Index product | Saves and returns, sets autocomplete suggestions |
| Delete product | Calls repository delete |
| Get by ID | Returns when found, empty when not found |

### Running Tests
```bash
cd search-service
mvn clean test
```

---

## Environment Setup

### Prerequisites
- Java 21 (verify with `java -version`)
- Maven (verify with `mvn -version`)
- Docker Desktop with Elasticsearch container running

### Running Locally
```bash
# Start infrastructure
cd Python-Microservices
docker-compose up -d

# Verify Elasticsearch
curl http://localhost:9200

# Build and run
cd search-service
mvn clean package -DskipTests
mvn spring-boot:run
```

### Configuration (`application.yml`)
```yaml
server:
  port: 8006

spring:
  elasticsearch:
    uris: http://localhost:9200

  kafka:
    bootstrap-servers: localhost:9092
    consumer:
      group-id: search-service-group
      auto-offset-reset: earliest
```

---

## Relationship with Other Services

```
Product Service (Python) ──► Kafka: product-updated ──► Search Service (Java) ──► Elasticsearch

API Gateway ──► GET /api/search?q=iphone ──► Search Service ──► Elasticsearch query ──► results
```

The Search Service has no direct dependency on the Product Service — they communicate exclusively through Kafka. If the Product Service is down, search still works with existing indexed data.

---

## Issues Encountered and Fixes

### Issue 1 — Lombok Annotation Processing Failed with Java 21

**What happened:** All Lombok annotations (`@Data`, `@Slf4j`, `@Builder`, `@RequiredArgsConstructor`) produced `cannot find symbol` compilation errors.

**Root cause:** Lombok's annotation processor wasn't being picked up by the Maven compiler plugin with Java 21. Even adding `annotationProcessorPaths` to the compiler plugin didn't resolve it.

**Fix:** Removed Lombok entirely. Wrote all getters, setters, constructors, and builders explicitly. This eliminates the dependency and makes the code transparent.

### Issue 2 — Elasticsearch Connection Refused on Startup

**What happened:** Spring Boot failed to start with `Connection refused` when creating the `productSearchRepository` bean.

**Root cause:** Docker Desktop wasn't running, so the Elasticsearch container wasn't available on `localhost:9200`.

**Fix:** Started Docker Desktop and ran `docker-compose up -d`. Spring Data Elasticsearch requires a running ES instance at startup to create the index.

### Issue 3 — Stale Docker Containers

**What happened:** `docker-compose up -d` failed with "container name already in use" for postgres and elasticsearch.

**Root cause:** Orphaned containers from previous runs that weren't properly removed.

**Fix:** `docker rm -f postgres elasticsearch` followed by `docker-compose up -d`.

---

## Key Lessons Learned

**Polyglot microservices work seamlessly via Kafka.** The Java Search Service and Python Product Service communicate through JSON events on Kafka — neither knows or cares about the other's language. This is the fundamental value of microservices.

**Elasticsearch is a read-optimized copy, not the source of truth.** MongoDB owns the product data. Elasticsearch is an index that can be rebuilt from Kafka events at any time. If ES goes down, products still exist — search is just temporarily unavailable.

**Remove Lombok when it causes friction.** Lombok saves typing but adds a dependency that can break with new Java versions. For a portfolio project, explicit code is clearer and more maintainable.

**Spring Data Elasticsearch handles index creation automatically.** The `@Document(indexName = "products")` annotation creates the index on startup if it doesn't exist, with field mappings derived from the `@Field` annotations. No manual index creation needed.