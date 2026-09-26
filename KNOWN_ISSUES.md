# Known Issues & TODOs

Open bugs and code/doc mismatches come first, then fixed issues, then the infrastructure roadmap. All were last checked against the repo on 2026-09-26. Issue numbers are stable: when an issue is fixed, its write-up moves into the Fixed table with a PR link, and the other issues keep their numbers.

# Open Issues

Found during a full end-to-end run (all 7 services plus infra, through the gateway with a Keycloak token) and two live Kafka-outage tests on 2026-09-26.

## 10. aiokafka consumer can stay stuck after an unclean Kafka restart

- **Where:** aiokafka consumers (notification, AI order-placed, AI cache invalidator)
- **Problem:** Observed once: after Docker Desktop quit uncleanly and Kafka came back (its first start crashed on a stale ZooKeeper broker registration, then recovered), an AI service consumer kept logging `GroupCoordinatorNotAvailableError` / `Heartbeat session expired` for 30+ minutes while Kafka and the consumer group were healthy. aiokafka retries this internally and never raises, so the retry loops from #33 don't restart it. That process ran pre-#33 code. A clean `docker stop kafka` / `docker start kafka`, both at startup and mid-run, recovered fine with #33.
- **Fix:** Try to reproduce (kill the Kafka container with `docker kill`, not `stop`). If it reproduces, add a watchdog that recreates the consumer when it has had no partition assignment for N minutes.

## 11. Cancelling an order doesn't restock inventory

- **Where:** `order-service/app/services/order_service.py` (`cancel_order`)
- **Problem:** Placing an order reduces stock over HTTP, but cancelling only sets the status and emits `order-cancelled`. Nothing gives the stock back (verified live: stock stayed at 8 after cancelling a 2-unit order from 10). The docs don't promise restocking, so this is a design decision, not a bug yet.
- **Fix:** Decide the intended behavior. If restocking is wanted, inventory-service could consume `order-cancelled` (the event already has the items), which keeps it async and idempotent.

## 12. AI recommendations can include the product you asked about

- **Where:** `ai-service/app/services/recommendation.py`
- **Problem:** `/recommendations?product_name=iPhone 15 Pro` sometimes returns "iPhone 15 Pro" itself. Minor, and model-dependent.
- **Fix:** Drop matches whose normalized name equals `product_name` in `get_recommendations`, before caching.

# Fixed Issues

| # | Issue | PR |
|---|---|---|
| 1 | AI Service Redis cache was documented but not implemented. LLM output validation landed first in #28 | #29 |
| 2 | Duplicate `ReconciliationJob` in Search Service ran every sync twice | #25 |
| 3 | Broken links in the README's "Service Documentation" table | #24 |
| 4 | AI Service defaulted to Gemini instead of Groq, and `factory.py` listed an OpenAI provider that didn't exist | #22 |
| 5 | Unit tests read the developer's local `.env` (e.g. `AUTH_ENABLED=true` failed 21 gateway tests). Fixed by `tests/conftest.py` in each service | #27 |
| 6 | `PATCH /api/orders/{id}/cancel` and `/status` always returned 500 and rolled back (`updated_at` expired by the flush, then lazy-loaded during serialization → `MissingGreenlet`). Re-cancelling also queued a second `order-cancelled` event | #31 |
| 7 | Search autocomplete returned 500 for any query containing a space, e.g. `iPhone 15` (`Criteria.contains()` rejects whitespace) | #32 |
| 8 | Kafka outages: aiokafka flooded logs (~700 MB/service; 3,477 lines/min from notification alone), notification and AI consumers died silently if Kafka was down at startup, product-service refused to start, and the order outbox never restarted its producer | #33 |
| 9 | AI and gateway unit tests wrote fake errors into the real `logs/<service>.log` (17 + 3 lines per run), which Promtail shipped to Loki. Each `tests/conftest.py` now points `LOG_DIR` at a temp dir | TBD |
| — | All six `app/config.py` typed `model_config` as pydantic's `ConfigDict` instead of `SettingsConfigDict` (Pylance errors, no runtime effect) | #30 |
| — | Groq retired `llama-3.3-70b-versatile` (404 `model_not_found`). Default switched to `openai/gpt-oss-120b` | #29 |
| — | Keycloak healthcheck never passed (no `curl` in image, wrong port, health endpoints disabled) | #26 |

---

# Roadmap / TODOs

Do these in order. Each step depends on the ones before it. The status of each was last checked against the repo on 2026-09-26.

## TODO 1 — Named volumes in Docker Compose · *mostly done*

**Status:** `mongo_data`, `postgres_data`, `prometheus_data`, `grafana_data`, `loki_data`, and `tempo_data` are already declared and mounted, so the core databases already survive `docker-compose down`/`up`. (`down -v` wipes them.)

**Remaining gaps:**
- [x] **Keycloak:** fixed in PR #21, which switched to `KC_DB: dev-file` and mounted `keycloak_data:/opt/keycloak/data`.
- [ ] **Elasticsearch:** no volume, so the index is rebuilt on restart. The reconcile job recovers it from Mongo within about 60s, so this is optional. Add `es_data:/usr/share/elasticsearch/data` if you want it to persist.
- [ ] **Redis:** no volume, so notification idempotency keys are lost on restart. That could cause duplicate emails if Kafka redelivers. (The AI cache in DB 1 is safe to lose, it just refills.) Add `redis_data:/data` and consider `--appendonly yes`.
- [ ] **Kafka/Zookeeper:** no volumes, so topics and consumer offsets are lost on restart. Undelivered events are safe because of the outbox, but consumers with `auto-offset-reset: earliest` will replay messages.
- [ ] If you add volumes, also add them to `REQUIRED_VOLUMES` in `.github/workflows/docker-validate.yml`.

## TODO 2 — All 7 app services in Docker Compose · *not started*

**Status:** compose only defines infrastructure. Every service has a Dockerfile, but they have the problems below.

**Blockers found:**
- [x] **No `.dockerignore` anywhere.** Fixed in #23: each Python service now has a `.dockerignore` excluding `.env*`, `venv/`, `tests/`, and caches. Still worth switching `api-gateway`, `notification-service`, and `ai-service` from `COPY . .` to the multi-stage `COPY app/ ./app/` pattern for consistency.
- [ ] **The search-service Dockerfile needs a prebuilt jar** (`COPY target/search-service-1.0.0.jar`). `docker compose build` fails on a clean checkout. Convert it to a multi-stage Maven build.
- [ ] **Hostnames:** every `config.py` and `application.yml` defaults to `localhost`. Set env overrides in compose, e.g. `MONGO_HOST=mongodb`, `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432` (internal port, not 5433), `KAFKA_BOOTSTRAP_SERVERS=kafka:29092` (internal listener), `REDIS_HOST=redis`, service URLs such as `http://inventory-service:8003`, `OTLP_ENDPOINT=http://tempo:4317`, and for search `SPRING_ELASTICSEARCH_URIS`, `SPRING_KAFKA_BOOTSTRAP_SERVERS`, and `PRODUCT_SERVICE_URL`.
- [ ] **Log path:** `logging_config.py` resolves `LOG_DIR` to `/logs` inside the container. Set `LOG_DIR` and mount `./logs`, or drop the file handler in containers and let Promtail read Docker stdout. Promtail's Docker scrape is currently broken (API version 1.42 is too old), so upgrading Promtail may be required.
- [ ] **Prometheus targets** point at `host.docker.internal:<port>`. Change them to service names, or keep a separate config for host mode.
- [ ] **Startup ordering:** use `depends_on: condition: service_healthy` on Postgres, Mongo, Kafka, and Keycloak. The Keycloak healthcheck works now (#26).
- [ ] **Secrets:** pass `GROQ_API_KEY` and SMTP credentials from the root `.env` or an `env_file:`. Don't bake them into images.
- [ ] Add the app services to `REQUIRED_SERVICES` in `docker-validate.yml`.

## TODO 3 — OpenTelemetry on Search Service (Java) · *not started*

**Status:** `pom.xml` has Actuator and Micrometer Prometheus but no tracing dependency, so traces stop at the gateway → search hop.

- [ ] Add `micrometer-tracing-bridge-otel` and `opentelemetry-exporter-otlp`, or attach the OTel Java agent.
- [ ] Configure `management.otlp.tracing.endpoint` (note: Spring's OTLP exporter defaults to **HTTP on 4318**, not gRPC on 4317). Set `management.tracing.sampling.probability: 1.0` for dev.
- [ ] Add `traceId`/`spanId` to the Logback pattern, ideally as JSON, so logs from search correlate in Loki the same way the Python services do.
- [ ] Check that the `product-updated` Kafka consumer and the `RestTemplate` calls in the reconcile job produce spans. `RestTemplate` must be built from `RestTemplateBuilder` for instrumentation to apply.

## TODO 4 — Port to Kubernetes (kind) · *not started*

**Status:** no `k8s/` directory and no manifests. Depends on TODO 2 (working images).

- [ ] Deployment and Service for each of the 7 app services, with readiness and liveness probes on `/health` (`/actuator/health` for search).
- [ ] StatefulSet and PVC for Postgres, Mongo, Elasticsearch, Kafka (consider KRaft to drop Zookeeper, or use the Strimzi operator), and Redis.
- [ ] ConfigMaps for the hostnames and URLs from TODO 2, and Secrets for DB passwords, `GROQ_API_KEY`, and SMTP. Load images into kind with `kind load docker-image`.
- [ ] Postgres init: mount `init-multiple-dbs.sh` from a ConfigMap. It must be executable, so set `defaultMode: 0755`.
- [ ] Observability: deploy Prometheus with `kubernetes_sd_configs` or pod annotations instead of static targets. Loki and Promtail should read pod stdout, which makes the `./logs` file handler unnecessary.
- [ ] Ingress (for example ingress-nginx) in front of `api-gateway`.

## TODO 5 — Helm chart (local + cloud values) · *not started*

Depends on TODO 4.

- [ ] Chart under `helm/`, with templated image tags, replicas, resources, and hostnames.
- [ ] `values-local.yaml` (kind: local images, `hostPath`/standard StorageClass, auth off) and `values-cloud.yaml` (ECR images, gp3 StorageClass, `AUTH_ENABLED=true`, ingress with TLS).
- [ ] Consider Bitnami subcharts for Postgres, Mongo, Redis, and Kafka instead of hand-written StatefulSets.

## TODO 6 — Horizontal Pod Autoscalers · *not started*

Depends on TODO 4. **Some services break or misbehave when scaled beyond one replica. Fix these first:**
- [ ] **Order Service outbox worker:** every replica runs `start_outbox_worker()`, and `_process_pending_events()` selects PENDING rows without locking. Two pods will publish the same event twice. Use `SELECT … FOR UPDATE SKIP LOCKED` (`.with_for_update(skip_locked=True)`), or run the worker as a separate single-replica Deployment.
- [ ] **Gateway rate limiting:** slowapi's `Limiter` in `api-gateway/app/middleware/rate_limit.py` uses in-memory storage, so each pod counts separately and the effective limit becomes N × 60/min. Point it at Redis (`storage_uri="redis://…"`).
- [ ] **Search reconcile job:** every replica runs the `@Scheduled` `DiffReconcileJob`. Add ShedLock, or run reconciliation as a Kubernetes CronJob.
- [ ] **Kafka consumer scaling:** topics are auto-created with 1 partition by default, so extra consumer replicas of notification, AI, or search sit idle. Pre-create topics with more partitions, or set `KAFKA_NUM_PARTITIONS`.
- [ ] Then set CPU requests and limits on each Deployment, install metrics-server on kind, and add HPAs for `api-gateway`, `product-service`, `order-service`, and `search-service`. Use a load generator (k6/hey) against `:9000` to show scaling, and add a Grafana panel for replica count.

## TODO 7 — Deploy to EKS · *not started*

Depends on TODO 5.

- [ ] Provision the cluster with `eksctl` or Terraform, install the EBS CSI driver (required for PVCs), and set up the AWS Load Balancer Controller for ingress.
- [ ] Push images to ECR. Extend `.github/workflows/ci.yml` to build and push on merge to `main`, which also finishes the "build → deploy" part of Phase 9 in the README.
- [ ] Store secrets in AWS Secrets Manager via External Secrets Operator, not plain k8s Secrets in git.
- [ ] Decide between managed services (RDS, MSK, OpenSearch, ElastiCache) and in-cluster StatefulSets. Managed is more realistic but costs more. Plan to tear everything down to control cost.
- [ ] Keycloak needs a real database (not `dev-file`) and `start` instead of `start-dev` for production mode.
