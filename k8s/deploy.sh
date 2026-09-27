#!/usr/bin/env bash
# Create (or update) the local kind cluster and deploy everything into namespace `ecommerce`.
# Needs: docker, kind, kubectl, helm. Safe to re-run; it rebuilds and reloads the images.
#
#   ./k8s/deploy.sh                 # full deploy
#   SKIP_BUILD=1 ./k8s/deploy.sh    # reuse images already loaded into kind
#   kind delete cluster --name ecommerce   # tear down (deletes all cluster data)
set -euo pipefail

cd "$(dirname "$0")/.."
CLUSTER=ecommerce
NS=ecommerce
TRAEFIK_CHART_VERSION=41.6.0
SERVICES=(api-gateway product-service order-service inventory-service notification-service ai-service search-service)

for tool in docker kind kubectl helm; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool" >&2; exit 1; }
done

if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --config k8s/kind-config.yaml
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

echo "── Traefik ingress controller"
helm repo add traefik https://traefik.github.io/charts >/dev/null 2>&1 || true
helm repo update traefik >/dev/null
helm upgrade --install traefik traefik/traefik --version "$TRAEFIK_CHART_VERSION" \
  --namespace traefik --create-namespace -f k8s/traefik-values.yaml --wait

if [ -z "${SKIP_BUILD:-}" ]; then
  echo "── Building and loading images"
  for svc in "${SERVICES[@]}"; do
    docker build -q -t "ecommerce/$svc:dev" "./$svc" >/dev/null
    kind load docker-image "ecommerce/$svc:dev" --name "$CLUSTER" >/dev/null
    echo "   $svc"
  done
fi

echo "── Secret and Postgres init script"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
[ -f k8s/secrets.env ] || { cp k8s/secrets.env.example k8s/secrets.env; echo "   created k8s/secrets.env from the example (edit it to add API keys)"; }
kubectl -n "$NS" create secret generic app-secrets --from-env-file=k8s/secrets.env \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$NS" create configmap postgres-init --from-file=docker/postgres/init-multiple-dbs.sh \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

echo "── Manifests"
# Pods read the Secret and images only at startup, so re-runs restart the Deployments.
# Not on the first install: a second set of pods would race the first on create_all.
existing=$(kubectl -n "$NS" get deployments -o name)
kubectl apply -k k8s/
if [ -n "$existing" ]; then
  kubectl -n "$NS" rollout restart deployment >/dev/null
fi

echo "── Waiting for rollouts"
for sts in postgres mongodb redis elasticsearch kafka; do
  kubectl -n "$NS" rollout status "statefulset/$sts" --timeout=300s
done
for svc in "${SERVICES[@]}"; do
  kubectl -n "$NS" rollout status "deployment/$svc" --timeout=300s
done

echo
echo "Ready: curl http://localhost:8080/health"
