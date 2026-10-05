#!/usr/bin/env bash
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python_bin="${QA_PYTHON:-python}"
output_dir="${QA_REPORT_DIR:-artifacts/reports}"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/nicedice-qa-reports.XXXXXX")"
trap 'rm -rf -- "$work_dir"' EXIT
mkdir -p "$output_dir"

overall_exit=0
for layer in unit component api contract; do
  "$python_bin" -m pytest -m "$layer" -q -p no:cacheprovider \
    --junitxml="$work_dir/${layer}.xml"
  layer_exit=$?
  if [[ $layer_exit -ne 0 ]]; then overall_exit=$layer_exit; fi
done

"$python_bin" -m pytest -m bug -q -p no:cacheprovider \
  --junitxml="$work_dir/bug.xml"
bug_exit=$?
if [[ $bug_exit -ne 0 ]]; then overall_exit=$bug_exit; fi

"$python_bin" -m pytest -q -p no:cacheprovider \
  --cov=src --cov-config=.coveragerc --cov-report="json:$work_dir/coverage.json" \
  --junitxml="$work_dir/full.xml"
full_exit=$?
if [[ $full_exit -ne 0 ]]; then overall_exit=$full_exit; fi

for layer in unit component api; do
  coverage_args=()
  if [[ "$layer" == "unit" ]]; then
    coverage_args=(
      --coverage "$work_dir/coverage.json"
      --full-junit "$work_dir/full.xml"
      --bug-junit "$work_dir/bug.xml"
    )
  fi
  "$python_bin" -m qa_reporting.cli layer --layer "$layer" \
    --junit "$work_dir/${layer}.xml" "${coverage_args[@]}" --output-dir "$output_dir" \
    || overall_exit=$?
done

contract_report_dir="$work_dir/contract-evidence"
CONTRACT_PYTHON="$python_bin" CONTRACT_REPORT_DIR="$contract_report_dir" \
  bash tests/contract/run_contract.sh
contract_exit=$?
if [[ $contract_exit -ne 0 ]]; then overall_exit=$contract_exit; fi
"$python_bin" -m qa_reporting.cli layer --layer contract \
  --junit "$work_dir/contract.xml" --contract-evidence "$contract_report_dir" \
  --output-dir "$output_dir" || overall_exit=$?
"$python_bin" -m qa_reporting.cli integration --output-dir "$output_dir" || overall_exit=$?

for security_check in sast sca secrets container config; do
  QA_PYTHON="$python_bin" SECURITY_RAW_DIR="artifacts/security" QA_REPORT_DIR="$output_dir" \
    bash scripts/run_security_check.sh "$security_check" || overall_exit=$?
done
if [[ -n "${ZAP_TARGET:-}" ]]; then
  QA_PYTHON="$python_bin" QA_REPORT_DIR="$output_dir" bash scripts/run_zap_local.sh || overall_exit=$?
else
  mkdir -p artifacts/security
  printf '{"site":[]}\n' > artifacts/security/zap.json
  "$python_bin" -m qa_reporting.cli security --check dast \
    --input artifacts/security/zap.json --scope "Local OpenAPI surface" \
    --network-safety NOT_APPLICABLE --execution-error "ZAP_TARGET was not supplied" \
    --output-dir "$output_dir" || overall_exit=$?
fi
"$python_bin" -m qa_reporting.cli security-aggregate --reports-dir "$output_dir" || overall_exit=$?
"$python_bin" -m qa_reporting.cli aggregate --reports-dir "$output_dir"
aggregate_exit=$?
if [[ $aggregate_exit -ne 0 ]]; then overall_exit=$aggregate_exit; fi

printf 'qa_reports=%s\n' "$output_dir"
exit "$overall_exit"
