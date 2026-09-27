# Known Issues & TODOs

Open bugs and code/doc mismatches come first, then fixed issues, then the infrastructure roadmap. All were last checked against the repo on 2026-09-26. Issue numbers are stable: when an issue is fixed, its write-up moves into the Fixed table with a PR link, and the other issues keep their numbers.

# Open Issues

Found during a full end-to-end run (all 7 services plus infra, through the gateway with a Keycloak token) and two live Kafka-outage tests on 2026-09-26.

None right now.

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
| 9 | AI and gateway unit tests wrote fake errors into the real `logs/<service>.log` (17 + 3 lines per run), which Promtail shipped to Loki. Each `tests/conftest.py` now points `LOG_DIR` at a temp dir | #35 |
| 10 | aiokafka consumer seemed stuck after an unclean Kafka restart (seen once, on pre-#33 code). **Closed, could not reproduce:** after `docker kill kafka`, and after killing Kafka + ZooKeeper together (Kafka's first start hit the same `NodeExists` crash, then restarted), all three consumer groups rejoined within ~30s and live events flowed end to end. If it comes back, add a watchdog that recreates a consumer with no partition assignment for N minutes | #37 |
| 11 | Cancelling an order didn't restock inventory. inventory-service now consumes `order-cancelled` and adds the stock back, idempotently (`processed_events` row in the same transaction), with offsets committed only after the restock commits | #38 |
| 12 | AI recommendations could include the product you asked about. Filtered out (normalized exact name) on both fresh and cached results, and the prompt now tells the model not to pick it | #37 |
| 13 | Nothing published `inventory-low`, but notification-service consumed it and the docs described low-stock alerts (README said inventory produced it, CLAUDE.md said AI). Feature removed: the consumer, email template, setting, and tests, plus the docs | #39 |
| — | All six `app/config.py` typed `model_config` as pydantic's `ConfigDict` instead of `SettingsConfigDict` (Pylance errors, no runtime effect) | #30 |
| — | Groq retired `llama-3.3-70b-versatile` (404 `model_not_found`). Default switched to `openai/gpt-oss-120b` | #29 |
| — | Keycloak healthcheck never passed (no `curl` in image, wrong port, health endpoints disabled) | #26 |

---

# Roadmap / TODOs

Do these in order. Each step depends on the ones before it. The status of each was last checked against the repo on 2026-09-26.

## TODO 1 — Named volumes in Docker Compose · *done (#41)*

**Status:** every stateful container has a named volume, so `docker compose down`/`up` keeps all data. Only `down -v` wipes it. Checked live: after `down`/`up`, the Elasticsearch index, Redis idempotency keys, Kafka topics and consumer offsets, and Postgres stock were all still there, and notification replayed nothing.

- [x] Mongo, Postgres, Prometheus, Grafana, Loki, Tempo: already had volumes.
- [x] Keycloak: `keycloak_data` with `KC_DB: dev-file` (#21).
- [x] Elasticsearch: `es_data`, so the index survives without waiting for the reconcile job.
- [x] Redis: `redis_data` plus `--appendonly yes`, so notification's idempotency keys survive restarts (no duplicate emails on Kafka redelivery).
- [x] Kafka/Zookeeper: `kafka_data`, `zookeeper_data`, `zookeeper_log`. These must be kept or wiped **together**: Kafka's `meta.properties` holds the cluster ID from Zookeeper, and a mismatch (`InconsistentClusterIdException`) stops Kafka from starting. To reset only Kafka, remove all three volumes.
- [x] All of them are in `REQUIRED_VOLUMES` in `docker-validate.yml`.

## TODO 2 — All 7 app services in Docker Compose · *done (#40)*

**Status:** `docker compose --profile apps up -d --build` runs infrastructure plus all 7 services. Plain `docker compose up -d` is still infrastructure only, for running services on the host. See the README's "Running the Application".

- [x] `.dockerignore` for every service (#23; search's added in #40). All Dockerfiles now use the same multi-stage, non-root layout with a healthcheck.
- [x] search-service builds its jar inside the image (multi-stage Maven), so a clean checkout builds.
- [x] Hostnames: container-network overrides in each service's `environment:` in `docker-compose.yml`, which win over the `<service>/.env` the container also loads. The gateway got `KEYCLOAK_INTERNAL_URL` for fetching signing keys, because the token issuer stays `http://localhost:8081`.
- [x] MongoDB auth: product-service got optional `MONGO_USERNAME`/`MONGO_PASSWORD`, and compose passes the root user. (The old "SCRAM fails over the Docker bridge" issue was a Homebrew `mongod` shadowing port 27017. See the CLAUDE.md Gotchas.)
- [x] Log path: containers set `LOG_DIR=/logs` and bind-mount `./logs`, so Promtail's existing file job ships them. Promtail's Docker scrape job is still broken (API 1.42). Leave it that way, or you'd get duplicate logs once it works.
- [x] Prometheus keeps scraping `host.docker.internal:<port>`, which works in both modes because the ports are published. Added `extra_hosts: host-gateway` for Linux.
- [x] Startup ordering: `depends_on: condition: service_healthy` on Mongo, Postgres, Kafka, Redis, and Elasticsearch.
- [x] Secrets come from the optional `env_file: <service>/.env`. Nothing is baked into images (`.dockerignore` excludes `.env*`).
- [x] `docker-validate.yml` checks the app services are defined and builds all 7 images.

## TODO 3 — OpenTelemetry on Search Service (Java) · *done (#42)*

**Status:** search-service exports traces to Tempo and writes JSON logs with `trace_id`/`span_id` that Promtail ships to Loki.

- [x] Added `micrometer-tracing-bridge-otel` and `opentelemetry-exporter-otlp` (versions from the Boot BOM).
- [x] `management.otlp.tracing.endpoint: http://localhost:4318/v1/traces` (OTLP HTTP; compose sets `tempo:4318`), sampling `1.0`. `/actuator/*` isn't traced, so healthchecks and Prometheus scrapes don't flood Tempo.
- [x] `logback-spring.xml` with `logstash-logback-encoder`: JSON with the Python field names, to stdout and `${LOG_DIR}/search-service.log` (10 MB x 3 rotation). Compose now mounts `./logs` for search too.
- [x] Checked in Tempo: gateway → search is one trace; `POST /api/products` → `product-updated send` → search's `product-updated receive` is one trace (`spring.kafka.listener.observation-enabled`); each reconcile run is a root span whose `RestTemplate` call continues into product-service.

## TODO 4 — Port to Kubernetes (kind) · *core done (#43); observability and Keycloak open*

**Status:** `k8s/deploy.sh` runs the 7 services and their data stores on kind (see `k8s/README.md`). The e2e flow (24 checks) passes through the ingress on `localhost:8080`.

- [x] Deployment and Service for each app, with probes on `/health`. Search uses Spring's `/actuator/health/{liveness,readiness}` groups, so an Elasticsearch outage doesn't restart it.
- [x] StatefulSets with PVCs for Postgres, Mongo, Elasticsearch, Redis (AOF), and Kafka in **KRaft** mode (no Zookeeper).
- [x] `app-config` ConfigMap for in-cluster hostnames, and the `app-secrets` Secret from the gitignored `k8s/secrets.env`. Images are loaded with `kind load docker-image`. Every Pod sets `enableServiceLinks: false` (CI checks it), because the injected `REDIS_PORT=tcp://...`-style variables break `Settings` and the Kafka image.
- [x] Postgres init script mounted from a ConfigMap with `defaultMode: 0755`.
- [x] Ingress in front of `api-gateway`, served by **Traefik** (ingress-nginx is archived).
- [ ] Observability: Tempo (then drop `OTEL_SDK_DISABLED` and `MANAGEMENT_TRACING_ENABLED=false`), Prometheus with `kubernetes_sd_configs` or pod annotations, Loki + Promtail reading pod stdout (then the `LOG_DIR` file handler isn't needed), and Grafana.
- [ ] Keycloak, so `AUTH_ENABLED=true` works in the cluster. The issuer URL must be the same for clients and the gateway, so serve Keycloak through the ingress too.
- [ ] The gateway rate limit is shared by all clients: requests come from Traefik's pod IP, and slowapi keys on `request.client.host`. Key on `X-Forwarded-For` (trusting only the ingress) or move rate limiting into Traefik.

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
- [ ] **Schema creation on startup races:** order and inventory run `Base.metadata.create_all` in `lifespan`, and search's Spring Data repository creates the `products` index on startup. Two pods starting at once against an empty database or ES both try to create them, and one crashes (`UniqueViolationError` on `pg_type`, `resource_already_exists_exception`) before succeeding on restart. Seen on kind when two ReplicaSets overlapped. Move schema setup into an init Job or migrations (Alembic), and create the index once (or tolerate "already exists").
- [ ] **Kafka consumer scaling:** topics are auto-created with 1 partition by default, so extra consumer replicas of notification, AI, or search sit idle. Pre-create topics with more partitions, or set `KAFKA_NUM_PARTITIONS`.
- [ ] Then set CPU requests and limits on each Deployment, install metrics-server on kind, and add HPAs for `api-gateway`, `product-service`, `order-service`, and `search-service`. Use a load generator (k6/hey) against `:9000` to show scaling, and add a Grafana panel for replica count.

## TODO 7 — Deploy to EKS · *not started*

Depends on TODO 5.

- [ ] Provision the cluster with `eksctl` or Terraform, install the EBS CSI driver (required for PVCs), and set up the AWS Load Balancer Controller for ingress.
- [ ] Push images to ECR. Extend `.github/workflows/ci.yml` to build and push on merge to `main`, which also finishes the "build → deploy" part of Phase 9 in the README.
- [ ] Store secrets in AWS Secrets Manager via External Secrets Operator, not plain k8s Secrets in git.
- [ ] Decide between managed services (RDS, MSK, OpenSearch, ElastiCache) and in-cluster StatefulSets. Managed is more realistic but costs more. Plan to tear everything down to control cost.
- [ ] Keycloak needs a real database (not `dev-file`) and `start` instead of `start-dev` for production mode.
