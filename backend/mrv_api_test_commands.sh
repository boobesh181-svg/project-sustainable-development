#!/usr/bin/env bash
set -euo pipefail

# Canonical API Test Commands (secured /api/v1)
#
# Notes:
# - Legacy ingestion endpoints under /api/mrv/* are disabled by default (ENABLE_MRV_INGESTION=false).
# - This script targets the ISO-style MRV approval workflow, emission factor governance, and
#   delivery evidence verification.

BASE_URL="http://localhost:8000"

echo "=== Canonical MRV API Tests ==="
echo "Base URL: $BASE_URL"

python_json_get() {
  python - <<'PY'
import json,sys
print(json.load(sys.stdin)["access_token"])
PY
}

echo "\n1) Login + capture tokens"
ADMIN_TOKEN=$(curl -sS -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}' | python_json_get)

ISSUER_TOKEN=$(curl -sS -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"mrv@example.com","password":"mrv123"}' | python_json_get)

VERIFIER_TOKEN=$(curl -sS -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"verifier@example.com","password":"verifier123"}' | python_json_get)

APPROVER_TOKEN=$(curl -sS -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"approver@example.com","password":"approver123"}' | python_json_get)

echo "  - ADMIN_TOKEN OK"
echo "  - ISSUER_TOKEN OK"
echo "  - VERIFIER_TOKEN OK"
echo "  - APPROVER_TOKEN OK"

echo "\n2) Discover a seeded project_id (DB query)"
PROJECT_ID=$(docker compose -f "backend/docker-compose.yml" exec -T db \
  psql -U windsurf -d windsurf -t -c "SELECT id FROM project ORDER BY created_at DESC LIMIT 1;" \
  | tr -d '[:space:]')
echo "  project_id=$PROJECT_ID"

echo "\n3) Admin creates + activates an emission factor"
FACTOR_ID=$(curl -sS -X POST "$BASE_URL/api/v1/emission-factors/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "material_code":"CEMENT_OPC",
    "material_name":"Cement (OPC)",
    "version": 1,
    "co2e_per_unit": 0.900000,
    "unit":"kg",
    "valid_from":"2025-01-01T00:00:00Z"
  }' | python - <<'PY'
import json,sys
print(json.load(sys.stdin)["id"])
PY
)
echo "  factor_id=$FACTOR_ID"

curl -sS -X POST "$BASE_URL/api/v1/emission-factors/$FACTOR_ID/activate" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' > /dev/null
echo "  activated"

echo "\n4) Issuer creates MRV report (DRAFT) referencing emission factor"
REPORT_ID=$(curl -sS -X POST "$BASE_URL/api/v1/mrv-approval/reports" \
  -H "Authorization: Bearer $ISSUER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\
    \"project_id\":\"$PROJECT_ID\",\
    \"reporting_period\":\"2025-Q1\",\
    \"sample_desc\":\"Batch-1 materials + transport\",\
    \"parameter\":\"scope3_materials\",\
    \"value\":\"cement_opc\",\
    \"total_co2e\": 12.345678,\
    \"emission_factor_id\":\"$FACTOR_ID\"\
  }" | python - <<'PY'
import json,sys
print(json.load(sys.stdin)["id"])
PY
)
echo "  report_id=$REPORT_ID"

echo "\n5) Advance workflow: DRAFT->SUBMITTED (issuer), SUBMITTED->VERIFIED (verifier), VERIFIED->APPROVED (approver), APPROVED->LOCKED (approver)"
curl -sS -X POST "$BASE_URL/api/v1/mrv-approval/reports/$REPORT_ID/advance" \
  -H "Authorization: Bearer $ISSUER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"next_status":"SUBMITTED"}' > /dev/null

curl -sS -X POST "$BASE_URL/api/v1/mrv-approval/reports/$REPORT_ID/advance" \
  -H "Authorization: Bearer $VERIFIER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"next_status":"VERIFIED"}' > /dev/null

curl -sS -X POST "$BASE_URL/api/v1/mrv-approval/reports/$REPORT_ID/advance" \
  -H "Authorization: Bearer $APPROVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"next_status":"APPROVED"}' > /dev/null

curl -sS -X POST "$BASE_URL/api/v1/mrv-approval/reports/$REPORT_ID/advance" \
  -H "Authorization: Bearer $APPROVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"next_status":"LOCKED"}' > /dev/null

echo "  locked"

echo "\n6) Delivery verification (evidence)"
TOKEN_ID=$(docker compose -f "backend/docker-compose.yml" exec -T db \
  psql -U windsurf -d windsurf -t -c "SELECT id FROM material_token WHERE redeemed = TRUE ORDER BY redeemed_at DESC NULLS LAST LIMIT 1;" \
  | tr -d '[:space:]')

if [ -z "$TOKEN_ID" ]; then
  echo "  No redeemed material_token found; seed data first (backend/scripts/seed_mrv.py)."
else
  echo "  material_token_id=$TOKEN_ID"
  VERIFY_ID=$(curl -sS -X POST "$BASE_URL/api/v1/deliveries/verify" \
    -H "Authorization: Bearer $ISSUER_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\
      \"material_token_id\":\"$TOKEN_ID\",\
      \"photo_path\":\"/uploads/material_evidence/demo_photo.jpg\",\
      \"delivery_lat\":12.9716,\
      \"delivery_lon\":77.5946\
    }" | python - <<'PY'
import json,sys
print(json.load(sys.stdin)["id"])
PY
  )
  echo "  delivery_verification_id=$VERIFY_ID"

  curl -sS -X POST "$BASE_URL/api/v1/deliveries/$VERIFY_ID/approve" \
    -H "Authorization: Bearer $VERIFIER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"verification_notes":"Approved after integrity checks"}' > /dev/null
  echo "  delivery verified"
fi

echo "\n=== Done ==="
