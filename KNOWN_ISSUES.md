# Known Issues & TODOs

The first part lists places where the code and the docs disagree, found while writing `CLAUDE.md` (2026-09-25). The second part is the infrastructure roadmap, checked against the repo on the same date.

## 1. AI Service Redis cache is documented but not implemented

- **Where:** `README.md` (Project Structure, "Redis Caching (Cache-Aside)", Resilience Patterns, Resume Highlights) vs `ai-service/app/`
- **Problem:** The README describes `ai-service/app/cache/redis_cache.py`: a cache-aside layer on Redis DB 1 with a 6h TTL for LLM product IDs, a 15min TTL for catalog data, and a graceful fallback. That module doesn't exist, and nothing in `ai-service/app` imports or uses Redis. `git log -S redis_cache` finds no commit that ever added it.
- **Fix:** Implement the cache (and add `redis` to `ai-service/requirements.txt`), or remove the claims from the README.

## 2. Two reconcile jobs run concurrently in Search Service

- **Where:** `search-service/src/main/java/com/ecommerce/search/scheduler/`
- **Problem:** `ReconciliationJob` and `DiffReconcileJob` are both `@Component`s. Each has `@Scheduled(fixedDelayString = "${reconciliation.interval.ms:1800000}")` and is gated by the same `reconciliation.enabled` flag, so both run every cycle. That means twice the reads from Product Service and Elasticsearch, and two jobs writing to ES at the same time. Only `DiffReconcileJob` has tests (`DiffReconcileJobTest`), and the README mentions only `DiffReconcileJob`.
- **Fix:** Delete `ReconciliationJob.java` if it's superseded, or give it its own enable flag.

## 3. Broken README links in "Service Documentation"

- **Where:** `README.md` → "📝 Service Documentation" table
- **Problem:** Several links point to files that don't exist:

  | README link | Actual file |
  |---|---|
  | `ai-service/ai-service-docs.md` | `ai-service/ai-docs.md` |
  | `api-gateway/api-gateway-docs.md` | `api-gateway/gw-docs.md` |
  | `search-service/search-service-docs.md` | `search-service/serarch-services-documentation.md` (typo in filename) |
  | `notification-service/notification-docs.md` | *(no doc file exists)* |

- **Fix:** Update the links, rename the search doc to fix the typo, and add a notification-service doc or drop that row.

## 4. AI Service defaults to Gemini, but the docs say Groq · ✅ fixed 2026-09-26

> The default is now `groq`. Factory and base-class docs list `groq, gemini, ollama`. The 45 AI tests pass with and without `.env`. The unused `OPENAI_*` settings were removed from `config.py`. Settings forbid unknown keys, so any local `ai-service/.env` must drop or comment out `OPENAI_API_KEY`/`OPENAI_MODEL`, or startup fails.

- **Where:** `ai-service/app/config.py` (`LLM_PROVIDER: str = "gemini"`) vs `README.md`
- **Problem:** The README says Groq/Llama 3.3 is the current provider and lists moving off Gemini (daily rate-limit exhaustion) as a fix. If `.env` doesn't set `LLM_PROVIDER`, the service still starts on Gemini. Also, the docstring and error message in `app/llm/factory.py` list `openai` as supported and call Groq "future". Neither is true: there is no OpenAI client, and Groq is implemented.
- **Fix:** Change the default to `"groq"` and update the text in `factory.py` so the supported providers are `gemini, groq, ollama`.

---

# Roadmap / TODOs

Do these in order. Each step depends on the ones before it. The status of each was checked against the repo on 2026-09-25.

## TODO 1 — Named volumes in Docker Compose · *mostly done*

**Status:** `mongo_data`, `postgres_data`, `prometheus_data`, `grafana_data`, `loki_data`, and `tempo_data` are already declared and mounted, so the core databases already survive `docker-compose down`/`up`. (`down -v` wipes them.)

**Remaining gaps:**
- [x] **Keycloak:** fixed in PR #21, which switched to `KC_DB: dev-file` and mounted `keycloak_data:/opt/keycloak/data`.
- [ ] **Elasticsearch:** no volume, so the index is rebuilt on restart. The reconcile job recovers it from Mongo within about 60s, so this is optional. Add `es_data:/usr/share/elasticsearch/data` if you want it to persist.
- [ ] **Redis:** no volume, so notification idempotency keys are lost on restart. That could cause duplicate emails if Kafka redelivers. Add `redis_data:/data` and consider `--appendonly yes`.
- [ ] **Kafka/Zookeeper:** no volumes, so topics and consumer offsets are lost on restart. Undelivered events are safe because of the outbox, but consumers with `auto-offset-reset: earliest` will replay messages.
- [ ] If you add volumes, also add them to `REQUIRED_VOLUMES` in `.github/workflows/docker-validate.yml`.

## TODO 2 — All 7 app services in Docker Compose · *not started*

**Status:** compose only defines infrastructure. Every service has a Dockerfile, but they have the problems below.

**Blockers found:**
- [ ] **No `.dockerignore` anywhere.** `api-gateway`, `notification-service`, and `ai-service` use `COPY . .`, which copies `venv/`, `tests/`, and **`.env` (containing secrets such as the Groq key and SMTP password)** into the image. Add a `.dockerignore` to each service, or switch them to the multi-stage `COPY app/ ./app/` pattern that product, order, and inventory already use.
- [ ] **The search-service Dockerfile needs a prebuilt jar** (`COPY target/search-service-1.0.0.jar`). `docker compose build` fails on a clean checkout. Convert it to a multi-stage Maven build.
- [ ] **Hostnames:** every `config.py` and `application.yml` defaults to `localhost`. Set env overrides in compose, e.g. `MONGO_HOST=mongodb`, `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432` (internal port, not 5433), `KAFKA_BOOTSTRAP_SERVERS=kafka:29092` (internal listener), `REDIS_HOST=redis`, service URLs such as `http://inventory-service:8003`, `OTLP_ENDPOINT=http://tempo:4317`, and for search `SPRING_ELASTICSEARCH_URIS`, `SPRING_KAFKA_BOOTSTRAP_SERVERS`, and `PRODUCT_SERVICE_URL`.
- [ ] **Log path:** `logging_config.py` resolves `LOG_DIR` to `/logs` inside the container. Set `LOG_DIR` and mount `./logs`, or drop the file handler in containers and let Promtail read Docker stdout. Promtail's Docker scrape is currently broken (API version 1.42 is too old), so upgrading Promtail may be required.
- [ ] **Prometheus targets** point at `host.docker.internal:<port>`. Change them to service names, or keep a separate config for host mode.
- [ ] **Startup ordering:** use `depends_on: condition: service_healthy` on Postgres, Mongo, and Kafka. Keycloak's healthcheck curls port `8081` inside the container, where it listens on `8080`, so it never passes.
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
- [ ] **Search reconcile jobs:** every replica runs the `@Scheduled` jobs, and so far two of them (see Issue 2). Add ShedLock, or run reconciliation as a Kubernetes CronJob.
- [ ] **Kafka consumer scaling:** topics are auto-created with 1 partition by default, so extra consumer replicas of notification, AI, or search sit idle. Pre-create topics with more partitions, or set `KAFKA_NUM_PARTITIONS`.
- [ ] Then set CPU requests and limits on each Deployment, install metrics-server on kind, and add HPAs for `api-gateway`, `product-service`, `order-service`, and `search-service`. Use a load generator (k6/hey) against `:9000` to show scaling, and add a Grafana panel for replica count.

## TODO 7 — Deploy to EKS · *not started*

Depends on TODO 5.

- [ ] Provision the cluster with `eksctl` or Terraform, install the EBS CSI driver (required for PVCs), and set up the AWS Load Balancer Controller for ingress.
- [ ] Push images to ECR. Extend `.github/workflows/ci.yml` to build and push on merge to `main`, which also finishes the "build → deploy" part of Phase 9 in the README.
- [ ] Store secrets in AWS Secrets Manager via External Secrets Operator, not plain k8s Secrets in git.
- [ ] Decide between managed services (RDS, MSK, OpenSearch, ElastiCache) and in-cluster StatefulSets. Managed is more realistic but costs more. Plan to tear everything down to control cost.
- [ ] Keycloak needs a real database (not `dev-mem`) and `start` instead of `start-dev` for production mode.
