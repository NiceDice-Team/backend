#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

python_bin="${CONTRACT_PYTHON:-python}"
schemathesis_bin="${CONTRACT_SCHEMATHESIS:-$(dirname "$python_bin")/schemathesis}"
if [[ ! -x "$schemathesis_bin" ]]; then
  schemathesis_bin="schemathesis"
fi
port="${CONTRACT_PORT:-18080}"
base_url="http://127.0.0.1:${port}"
report_dir="${CONTRACT_REPORT_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/nicedice-contract-report.XXXXXX")}"
database_file=""
server_pid=""

cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  if [[ -n "$database_file" && "${CONTRACT_PRESERVE_DATABASE:-0}" != "1" ]]; then
    rm -f -- "$database_file"
  fi
}
trap cleanup EXIT

mkdir -p "$report_dir"
if [[ "${CONTRACT_USE_POSTGRES:-0}" != "1" ]]; then
  database_file="$(mktemp "${TMPDIR:-/tmp}/nicedice-contract-db.XXXXXX.sqlite3")"
  export CONTRACT_SQLITE_PATH="$database_file"
fi

export DJANGO_SETTINGS_MODULE=src.contract_settings
export CONTRACT_EGRESS_GUARD=1
export PYTHONPATH="$repo_root/tests/contract/network_guard:$repo_root:$repo_root/src${PYTHONPATH:+:$PYTHONPATH}"
export CONTRACT_EMAIL_BACKEND="${CONTRACT_EMAIL_BACKEND:-django.core.mail.backends.locmem.EmailBackend}"
export CONTRACT_EMAIL_HOST="${CONTRACT_EMAIL_HOST:-127.0.0.1}"
export CONTRACT_FRONTEND_BASE_URL="${CONTRACT_FRONTEND_BASE_URL:-http://127.0.0.1:8000}"
export CONTRACT_ALLOWED_LOCAL_HOSTS="${CONTRACT_ALLOWED_LOCAL_HOSTS:-}"
export AWS_ACCESS_KEY_ID=""
export AWS_SECRET_ACCESS_KEY=""
export AWS_SESSION_TOKEN=""
export STRIPE_SECRET_KEY=""
export GOOGLE_OAUTH2_CLIENT_ID=""
export GOOGLE_OAUTH2_CLIENT_SECRET=""
export FACEBOOK_APP_ID=""
export FACEBOOK_APP_SECRET=""

"$python_bin" tests/contract/verify_network_guard.py
"$python_bin" tests/contract/verify_contract_environment.py
"$python_bin" tests/contract/check_schema_validation.py \
  --baseline tests/contract/baselines/schema_validation.json \
  --output "$report_dir/schema-validation.json" \
  --log "$report_dir/schema-validation.log"
"$python_bin" manage.py migrate --noinput >"$report_dir/migrate.log" 2>&1
auth_token="$("$python_bin" tests/contract/seed_contract_data.py)"
test -n "$auth_token"

"$python_bin" manage.py runserver "127.0.0.1:${port}" --noreload \
  >"$report_dir/django.log" 2>&1 &
server_pid=$!
for _ in {1..30}; do
  if curl --fail --silent "$base_url/api/schema/" >"$report_dir/schema.json"; then
    break
  fi
  sleep 1
done
curl --fail --silent "$base_url/api/schema/" >"$report_dir/schema.json"
"$python_bin" manage.py spectacular --file "$report_dir/schema.yaml" \
  >"$report_dir/schema-generation.log" 2>&1

set +e
"$schemathesis_bin" run "$base_url/api/schema/" \
  --url "$base_url" \
  --header "Authorization: Bearer ${auth_token}" \
  --mode all \
  --phases examples,coverage,fuzzing \
  --checks not_a_server_error,status_code_conformance,content_type_conformance,response_headers_conformance,response_schema_conformance,negative_data_rejection,positive_data_acceptance \
  --exclude-operation-id users_oauth_create \
  --exclude-operation-id orders_create_payment_intent_create \
  --workers 1 \
  --max-examples 10 \
  --seed 20261003 \
  --generation-deterministic \
  --max-redirects 0 \
  --report junit \
  --report-junit-path "$report_dir/junit.xml" \
  >"$report_dir/schemathesis-output.txt" 2>&1
schemathesis_exit=$?
set -e
echo "$schemathesis_exit" >"$report_dir/schemathesis-exit-code.txt"
test -s "$report_dir/junit.xml"

"$python_bin" tests/contract/normalize_schemathesis.py \
  --junit "$report_dir/junit.xml" \
  --schema "$report_dir/schema.yaml" \
  --baseline tests/contract/baselines/runtime_failures.json \
  --output "$report_dir/normalized-failures.json"
"$python_bin" tests/contract/build_operation_matrix.py \
  --junit "$report_dir/junit.xml" \
  --schema "$report_dir/schema.yaml" \
  --baseline tests/contract/baselines/runtime_failures.json \
  --output "$report_dir/operation-matrix.json"

printf 'contract_report=%s\n' "$report_dir"
