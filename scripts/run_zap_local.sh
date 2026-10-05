#!/usr/bin/env bash
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python_bin="${QA_PYTHON:-python}"
target="${ZAP_TARGET:-}"
if [[ -z "$target" ]]; then
  echo "ZAP_TARGET is required and must identify disposable local infrastructure" >&2
  exit 2
fi
"$python_bin" - <<'PY' "$target"
import ipaddress, sys
from urllib.parse import urlparse
p=urlparse(sys.argv[1])
allowed={"localhost","host.docker.internal"}
try: local=ipaddress.ip_address(p.hostname or "").is_loopback
except ValueError: local=(p.hostname or "").lower() in allowed
if p.scheme not in {"http","https"} or not local:
    raise SystemExit("ZAP_TARGET must be loopback or host.docker.internal")
PY
target_port="$("$python_bin" -c 'import sys; from urllib.parse import urlparse; p=urlparse(sys.argv[1]); print(p.port or (443 if p.scheme == "https" else 80))' "$target")"

mkdir -p artifacts/security artifacts/reports
rm -f artifacts/security/zap.json artifacts/security/zap.html
started=$SECONDS
scan_exit=0
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v "$repo_root/artifacts/security:/zap/wrk/:rw" ghcr.io/zaproxy/zaproxy:2.16.1 \
  zap-api-scan.py -S -t "$target" -f openapi -J zap.json -r zap.html -I \
  >/tmp/nicedice-zap.log 2>&1 || scan_exit=$?
duration=$((SECONDS - started))

network="FAILED"
if [[ -f artifacts/security/zap.json ]] && \
   "$python_bin" scripts/verify_zap_targets.py artifacts/security/zap.json \
     --allow-origin "$target" \
     --allow-origin "${ZAP_FRONTEND_ORIGIN:-http://127.0.0.1:$target_port}"; then
  network="PASSED"
fi
error_args=()
if (( scan_exit > 2 )) || [[ ! -f artifacts/security/zap.json ]]; then
  error_args=(--execution-error "ZAP execution failed with exit code $scan_exit")
  test -f artifacts/security/zap.json || printf '{"site":[]}\n' > artifacts/security/zap.json
fi
command=("$python_bin" -m qa_reporting.cli security --check dast \
  --input artifacts/security/zap.json --version "ZAP 2.16.1 container" \
  --duration "$duration" --exit-code "$scan_exit" \
  --scope "OpenAPI public surface; safe/passive API scan; authentication not configured" \
  --network-safety "$network" --output-dir artifacts/reports)
if (( ${#error_args[@]} )); then command+=("${error_args[@]}"); fi
"${command[@]}"
