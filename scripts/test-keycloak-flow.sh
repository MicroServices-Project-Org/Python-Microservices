#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# test-keycloak-flow.sh
#
# End-to-end verification of the Keycloak auth flow for the CartVista API
# Gateway. Asserts on status codes and JWT claims — exits non-zero on any
# failure so it can be used as a regression gate (locally or in CI).
#
# Prerequisites:
#   - docker-compose up -d  (Keycloak on :8081 with microservices realm)
#   - API Gateway running on :9000 with AUTH_ENABLED=true
#
# Usage:
#   ./test-keycloak-flow.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8081}"
REALM="${REALM:-microservices}"
CLIENT_ID="${CLIENT_ID:-api-gateway}"
USERNAME="${USERNAME:-testuser}"
PASSWORD="${PASSWORD:-testpass}"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:9000}"
PROTECTED_PATH="${PROTECTED_PATH:-/api/products}"

# ─── pretty output ───────────────────────────────────────────────────────────
RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
pass() { echo "${GREEN}✓${NC} $1"; }
fail() { echo "${RED}✗${NC} $1"; exit 1; }
step() { echo; echo "${YELLOW}── $1 ──${NC}"; }

assert_eq() {
  local actual="$1" expected="$2" msg="$3"
  if [ "$actual" = "$expected" ]; then
    pass "$msg (got $actual)"
  else
    fail "$msg (expected $expected, got $actual)"
  fi
}

# ─── Step 1: realm discovery endpoint reachable ──────────────────────────────
step "Step 1: Realm discovery endpoint"
ISSUER=$(curl -fsS "${KEYCLOAK_URL}/realms/${REALM}/.well-known/openid-configuration" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['issuer'])") \
  || fail "Could not reach realm discovery endpoint at ${KEYCLOAK_URL}/realms/${REALM}"
assert_eq "$ISSUER" "${KEYCLOAK_URL}/realms/${REALM}" "Issuer matches expected URL"

# ─── Step 2: token issuance ──────────────────────────────────────────────────
step "Step 2: Token issuance (password grant)"
TOKEN_RESPONSE=$(curl -fsS -X POST \
  "${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=${CLIENT_ID}" \
  -d "username=${USERNAME}" \
  -d "password=${PASSWORD}" \
  -d "scope=openid") \
  || fail "Token request failed — check client config and user credentials"

TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
[ -n "$TOKEN" ] || fail "No access_token in response: $TOKEN_RESPONSE"
pass "Access token issued (length: ${#TOKEN} chars)"

# ─── Step 3: JWT claim inspection ────────────────────────────────────────────
step "Step 3: JWT claim inspection"
CLAIMS=$(echo "$TOKEN" | cut -d. -f2 | python3 -c "
import sys, base64, json
s = sys.stdin.read().strip()
print(base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode())
")

claim() { echo "$CLAIMS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$1',''))"; }

assert_eq "$(claim iss)" "${KEYCLOAK_URL}/realms/${REALM}" "Issuer (iss) claim"
assert_eq "$(claim azp)" "${CLIENT_ID}"                    "Authorized party (azp) claim"
assert_eq "$(claim preferred_username)" "${USERNAME}"      "preferred_username claim"
assert_eq "$(claim typ)" "Bearer"                          "Token type"

ROLES=$(echo "$CLAIMS" | python3 -c "import sys,json; print(','.join(json.load(sys.stdin).get('realm_access',{}).get('roles',[])))")
echo "$ROLES" | grep -q "user" && pass "realm_access.roles contains 'user' (got: $ROLES)" \
  || fail "realm_access.roles missing 'user' (got: $ROLES)"

# ─── Step 4: gateway accepts a valid token ───────────────────────────────────
step "Step 4: Gateway accepts valid token"
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  "${GATEWAY_URL}${PROTECTED_PATH}")
assert_eq "$CODE" "200" "GET ${PROTECTED_PATH} with valid token"

# ─── Step 5: gateway rejects invalid/missing tokens ──────────────────────────
step "Step 5: Gateway rejects bad tokens"
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer not.a.real.token" \
  "${GATEWAY_URL}${PROTECTED_PATH}")
assert_eq "$CODE" "401" "GET ${PROTECTED_PATH} with malformed token"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "${GATEWAY_URL}${PROTECTED_PATH}")
assert_eq "$CODE" "401" "GET ${PROTECTED_PATH} with no Authorization header"

CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Token $TOKEN" \
  "${GATEWAY_URL}${PROTECTED_PATH}")
assert_eq "$CODE" "401" "GET ${PROTECTED_PATH} without 'Bearer' prefix"

echo
echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${GREEN}  All Keycloak auth flow checks passed ✓${NC}"
echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"