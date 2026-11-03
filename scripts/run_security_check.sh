#!/usr/bin/env bash
set -uo pipefail

check="${1:?usage: run_security_check.sh sast|sca|secrets|container|config}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python_bin="${QA_PYTHON:-python}"
raw_dir="${SECURITY_RAW_DIR:-artifacts/security}"
report_dir="${QA_REPORT_DIR:-artifacts/reports}"
mkdir -p "$raw_dir" "$report_dir"
started=$SECONDS
scan_exit=0
version="unknown"
scope=""
raw=""
expected_max=1

case "$check" in
  sast)
    raw="$raw_dir/bandit.json"
    scope="Production Python source; excludes migrations, local test suites/settings, and the test-data fixture loader"
    version="$(bandit --version 2>/dev/null | head -1 || true)"
    bandit -r src -f json -o "$raw" \
      -x "src/categories/tests,src/users/tests,src/products/migrations,src/users/migrations,src/cart/migrations,src/orders/migrations,src/categories/migrations,src/contract_settings.py,src/test_settings.py,src/core/management/commands/load_test_data.py" \
      >/dev/null 2>&1 || scan_exit=$?
    ;;
  sca)
    raw="$raw_dir/pip-audit.json"
    scope="Runtime dependencies resolved from requirements.txt (requirements are not lock-pinned)"
    version="$(pip-audit --version 2>/dev/null || true)"
    pip-audit -r requirements.txt -f json -o "$raw" >/dev/null 2>&1 || scan_exit=$?
    ;;
  secrets)
    raw="$raw_dir/gitleaks.json"
    scope="Tracked repository history and working tree metadata; values redacted"
    if command -v gitleaks >/dev/null; then
      version="$(gitleaks version 2>/dev/null || true)"
      gitleaks detect --source . --redact --no-banner --report-format json --report-path "$raw" \
        >/dev/null 2>&1 || scan_exit=$?
    else
      version="gitleaks 8.24.2 (container)"
      docker run --rm -v "$repo_root:/repo" ghcr.io/gitleaks/gitleaks:v8.24.2 \
        detect --source=/repo --redact --no-banner --report-format=json --report-path=/repo/$raw \
        >/dev/null 2>&1 || scan_exit=$?
    fi
    test -f "$raw" || printf '[]\n' > "$raw"
    ;;
  container)
    raw="$raw_dir/trivy.json"
    scope="Repository filesystem, runtime dependencies, Dockerfiles and Compose misconfiguration"
    if command -v trivy >/dev/null; then
      version="$(trivy --version 2>/dev/null | head -1 || true)"
      trivy fs --scanners vuln,misconfig --format json --output "$raw" \
        --skip-dirs .git --skip-dirs artifacts --skip-dirs .venv --skip-dirs venv . \
        >/dev/null 2>&1 || scan_exit=$?
    else
      version="Trivy 0.75.0 (container)"
      docker run --rm -v "$repo_root:/repo" aquasec/trivy:0.75.0 fs \
        --scanners vuln,misconfig --format json --output /repo/$raw \
        --skip-dirs /repo/.git --skip-dirs /repo/artifacts --skip-dirs /repo/.venv /repo \
        >/dev/null 2>&1 || scan_exit=$?
    fi
    expected_max=0
    ;;
  config)
    raw="$raw_dir/django-check.txt"
    scope="Django deploy checks using fail-closed local contract settings"
    version="$($python_bin -c 'import django; print(django.get_version())' 2>/dev/null || true)"
    CONTRACT_SQLITE_PATH="${TMPDIR:-/tmp}/nicedice-security-check.sqlite3" \
      DJANGO_SETTINGS_MODULE=src.contract_settings \
      "$python_bin" manage.py check --deploy >"$raw" 2>&1 || scan_exit=$?
    expected_max=0
    ;;
  *)
    echo "unsupported security check: $check" >&2
    exit 2
    ;;
esac

duration=$((SECONDS - started))
error_args=()
if (( scan_exit > expected_max )) || [[ ! -f "$raw" ]]; then
  error_args=(--execution-error "scanner execution failed with exit code $scan_exit")
  if [[ ! -f "$raw" ]]; then
    if [[ "$check" == config ]]; then printf '' > "$raw"; else printf '{}\n' > "$raw"; fi
  fi
fi

command=("$python_bin" -m qa_reporting.cli security --check "$check" --input "$raw"
  --version "$version" --duration "$duration" --exit-code "$scan_exit" --scope "$scope"
  --output-dir "$report_dir")
if (( ${#error_args[@]} )); then command+=("${error_args[@]}"); fi
"${command[@]}"
