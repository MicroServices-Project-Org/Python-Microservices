# Kubernetes (kind)

Runs the 7 app services and their data stores on a local [kind](https://kind.sigs.k8s.io/) cluster, in namespace `ecommerce`. This is the Kubernetes version of `docker compose --profile apps up`. Observability (Prometheus, Loki, Tempo, Grafana) and Keycloak aren't in the cluster yet (see KNOWN_ISSUES TODO 4).

## Requirements

`docker`, `kind`, `kubectl`, and `helm` on your PATH. Give Docker Desktop at least 6 GB of memory. Stop the Compose stack first (`docker compose --profile apps down`, which keeps its volumes), because both together don't fit in 8 GB.

## Deploy

```bash
./k8s/deploy.sh                  # create the cluster, build and load images, apply everything
curl http://localhost:8080/health
curl http://localhost:8080/api/products
```

`deploy.sh` is safe to re-run. It:
1. Creates the kind cluster `ecommerce` from `kind-config.yaml` if it doesn't exist.
2. Installs the Traefik ingress controller with Helm (`traefik-values.yaml`, on NodePort 30080, which kind maps to `localhost:8080`).
3. Builds the 7 images as `ecommerce/<service>:dev` and loads them into kind (`SKIP_BUILD=1` skips this).
4. Creates the `app-secrets` Secret from `k8s/secrets.env` (gitignored; copied from `secrets.env.example` on first run) and the `postgres-init` ConfigMap from `docker/postgres/init-multiple-dbs.sh`.
5. Runs `kubectl apply -k k8s/`, restarts the Deployments, and waits for every rollout.

To add an API key, edit `k8s/secrets.env` (for example `GROQ_API_KEY=...`) and re-run `SKIP_BUILD=1 ./k8s/deploy.sh`.

## Layout

| Path | What |
|---|---|
| `kind-config.yaml` | Single-node cluster; host port 8080 → Traefik |
| `traefik-values.yaml` | Helm values for Traefik (ingress-nginx is archived) |
| `config.yaml` | `app-config` ConfigMap: in-cluster hostnames and URLs, shared by the Python services via `envFrom` |
| `secrets.env.example` | Keys for the `app-secrets` Secret (DB credentials, LLM API keys, SMTP) |
| `infra/` | StatefulSets with PVCs: Postgres, MongoDB, Redis (AOF), Elasticsearch, Kafka (KRaft, no Zookeeper) |
| `apps/` | Deployment + Service per app, with `/health` probes (`/actuator/health/{liveness,readiness}` for search) |
| `ingress.yaml` | Routes everything to `api-gateway:9000` |

## Things to know

- **`enableServiceLinks: false` on every Pod.** Otherwise Kubernetes injects variables like `REDIS_PORT=tcp://10.96.x.x:6379` for each Service, which break `Settings` (it expects an int) and the Confluent Kafka image (it turns every `KAFKA_*` variable into broker config). CI checks for this.
- **Auth is off** (`AUTH_ENABLED` defaults to `false`) because Keycloak isn't deployed.
- **Tracing is off** (`OTEL_SDK_DISABLED=true`, `MANAGEMENT_TRACING_ENABLED=false`) until Tempo is deployed. Logs go to stdout (`kubectl logs`); the file handler writes to `/tmp/logs` in the container.
- **The gateway's rate limit is shared by all clients.** Requests reach it from Traefik's pod IP, and slowapi keys on the client address.
- Data lives in PVCs (kind's `standard` local-path StorageClass), so it survives pod restarts and re-deploys. `kind delete cluster --name ecommerce` deletes it. The cluster doesn't share data with the Compose volumes.
- Pods wait for their database with an init container (`busybox`), and services retry Kafka on their own, so start-up order doesn't matter.

## Useful commands

```bash
kubectl -n ecommerce get pods
kubectl -n ecommerce logs deploy/order-service -f
kubectl -n ecommerce rollout restart deploy/product-service    # after `kind load` of a new image
kubectl -n ecommerce port-forward svc/postgres 5433:5432         # psql from the host
kind delete cluster --name ecommerce
```
