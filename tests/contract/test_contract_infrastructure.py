import json
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract
BASELINES = Path(__file__).with_name("baselines")


def test_runtime_baseline_preserves_reviewed_root_cause_registry():
    baseline = json.loads((BASELINES / "runtime_failures.json").read_text())

    assert set(baseline["reviewed_root_causes"]) == {f"RC-{number:02d}" for number in range(1, 19)}
    assert Counter(
        value["classification"] for value in baseline["reviewed_root_causes"].values()
    ) == {
        "Implementation": 5,
        "OpenAPI/schema": 5,
        "Both": 5,
        "Test-data/setup": 2,
        "Tooling": 1,
    }


def test_runtime_baseline_links_existing_deterministic_5xx_findings():
    baseline = json.loads((BASELINES / "runtime_failures.json").read_text())

    assert {
        baseline["reviewed_root_causes"][root]["nd_be_id"]
        for root in ("RC-01", "RC-02", "RC-03", "RC-04")
    } == {"ND-BE-018", "ND-BE-020", "ND-BE-021", "ND-BE-022"}


def test_exclusions_are_exact_and_do_not_expand_silently():
    baseline = json.loads((BASELINES / "runtime_failures.json").read_text())
    runner = Path(__file__).with_name("run_contract.sh").read_text()

    assert baseline["excluded_operations"] == [
        "users_oauth_create",
        "orders_create_payment_intent_create",
    ]
    assert runner.count("--exclude-operation-id") == 2
    assert "--exclude-operation-id users_oauth_create" in runner
    assert "--exclude-operation-id orders_create_payment_intent_create" in runner
