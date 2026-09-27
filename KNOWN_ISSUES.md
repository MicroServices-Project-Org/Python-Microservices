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
