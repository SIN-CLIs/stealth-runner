"""Tests for .github/workflows/schema-guard.yml (SR-121).

Pure YAML-structure linting — no docker, no actual workflow invocation.
PyYAML is required (available in standard CI test envs).
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip(
    "yaml",
    reason="PyYAML required to lint workflow YAML structure",
)


WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "schema-guard.yml"


@pytest.fixture(scope="module")
def workflow_doc() -> dict:
    """Parse the workflow YAML once per module."""
    assert WORKFLOW_PATH.exists(), f"schema-guard workflow not found at {WORKFLOW_PATH}"
    with WORKFLOW_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def workflow_text() -> str:
    """Raw text — useful when checking the literal `if: always()` token,
    which PyYAML would normalise away."""
    assert WORKFLOW_PATH.exists()
    return WORKFLOW_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T1 — YAML is parseable
# ---------------------------------------------------------------------------


def test_t1_yaml_is_parseable(workflow_doc):
    assert isinstance(workflow_doc, dict)
    # The `on:` key gets parsed by PyYAML as the boolean `True` because
    # YAML 1.1 treats bare `on` as a truthy token. Accept either spelling
    # and prove the structural shape is intact.
    assert "name" in workflow_doc
    assert "jobs" in workflow_doc
    assert (True in workflow_doc) or ("on" in workflow_doc)


# ---------------------------------------------------------------------------
# T2 — has on.pull_request and on.push.branches == [main]
# ---------------------------------------------------------------------------


def _on_block(doc: dict) -> dict:
    """Return the `on:` mapping, accounting for YAML 1.1 boolean coercion."""
    if "on" in doc:
        return doc["on"]
    return doc[True]


def test_t2_triggers_pull_request_and_push_to_main(workflow_doc):
    on_block = _on_block(workflow_doc)
    assert isinstance(on_block, dict), f"on: must be a mapping, got {on_block!r}"

    # pull_request must be a trigger key (value can be None or {}).
    assert "pull_request" in on_block

    # push.branches must include main.
    push = on_block.get("push")
    assert push is not None, "on.push trigger required"
    branches = push.get("branches")
    assert branches is not None, "on.push.branches required"
    assert "main" in branches, f"on.push.branches must include 'main', got {branches!r}"


# ---------------------------------------------------------------------------
# T3 — uses actions/checkout@v5 (not @latest, not @master)
# ---------------------------------------------------------------------------


def _all_uses(doc: dict) -> list[str]:
    """Walk all `uses:` strings across all jobs/steps."""
    out: list[str] = []
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if "uses" in step:
                out.append(step["uses"])
    return out


def test_t3_uses_checkout_v5(workflow_doc):
    uses = _all_uses(workflow_doc)
    checkout = [u for u in uses if u.startswith("actions/checkout@")]
    assert checkout, "actions/checkout step must be present"
    for ref in checkout:
        assert ref == "actions/checkout@v5", (
            f"checkout must be pinned to @v5 per AGENTS.md §13.8.4, got {ref!r}"
        )


# ---------------------------------------------------------------------------
# T4 — uses actions/setup-python@v6 (not @latest, not @master)
# ---------------------------------------------------------------------------


def test_t4_uses_setup_python_v6(workflow_doc):
    uses = _all_uses(workflow_doc)
    setup = [u for u in uses if u.startswith("actions/setup-python@")]
    assert setup, "actions/setup-python step must be present"
    for ref in setup:
        assert ref == "actions/setup-python@v6", (
            f"setup-python must be pinned to @v6 per AGENTS.md §13.8.4, got {ref!r}"
        )


# ---------------------------------------------------------------------------
# T5 — both validator scripts invoked with --exit-non-zero-on-violation
# ---------------------------------------------------------------------------


def test_t5_both_validators_invoked_with_exit_non_zero(workflow_text):
    # Both scripts must appear in a `run:` block AND be flagged with
    # --exit-non-zero-on-violation. Plain substring is fine — these are
    # well-known fixed tokens, not user input.
    assert "scripts/check_audit_log_schema.py" in workflow_text, (
        "audit-log validator script must be invoked"
    )
    assert "scripts/check_inbox_log_schema.py" in workflow_text, (
        "inbox-log validator script must be invoked"
    )
    assert workflow_text.count("--exit-non-zero-on-violation") >= 2, (
        "both validators must be flagged --exit-non-zero-on-violation "
        f"(found {workflow_text.count('--exit-non-zero-on-violation')})"
    )


# ---------------------------------------------------------------------------
# T6 — has `if: always()` upload-artifact step with retention-days: 14
# ---------------------------------------------------------------------------


def test_t6_upload_artifact_if_always_retention_14(workflow_doc, workflow_text):
    # Find the upload-artifact step in the parsed doc.
    upload_step = None
    for job in (workflow_doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            uses = step.get("uses", "")
            if uses.startswith("actions/upload-artifact@"):
                upload_step = step
                break
        if upload_step is not None:
            break

    assert upload_step is not None, "upload-artifact step required"
    # Pinned major version (AC: actions/upload-artifact@v4).
    assert upload_step["uses"] == "actions/upload-artifact@v4", (
        f"upload-artifact must be @v4, got {upload_step['uses']!r}"
    )
    # `if: always()` is the literal YAML token — when PyYAML loads it
    # the value becomes the string "always()" (not a callable).
    assert upload_step.get("if") == "always()", (
        f"upload-artifact step must guard with `if: always()`, got {upload_step.get('if')!r}"
    )
    # retention-days: 14.
    with_block = upload_step.get("with") or {}
    assert with_block.get("retention-days") == 14, (
        f"retention-days must be 14, got {with_block.get('retention-days')!r}"
    )
    # Sanity-check that both JSON reports are in the upload path. The
    # `path:` value is a multi-line scalar — accept either a string with
    # newlines or a list.
    path_value = with_block.get("path", "")
    path_text = "\n".join(path_value) if isinstance(path_value, list) else str(path_value)
    assert "audit-schema.json" in path_text
    assert "inbox-schema.json" in path_text


# ---------------------------------------------------------------------------
# Hardening — extras
# ---------------------------------------------------------------------------


def test_h1_no_at_latest_or_at_master_references(workflow_doc):
    """AGENTS.md §13.8.4 forbids @latest / @master in action `uses:` refs."""
    for ref in _all_uses(workflow_doc):
        assert "@latest" not in ref, f"AGENTS.md §13.8.4 forbids `@latest` action refs, got {ref!r}"
        assert "@master" not in ref, f"AGENTS.md §13.8.4 forbids `@master` action refs, got {ref!r}"


def test_h2_no_pip_install_step(workflow_text):
    """AC3: validators are stdlib-only — must NOT install requirements."""
    forbidden = [
        "pip install -r",
        "pip install pytest",
        "pip install ruff",
        "pip install mypy",
    ]
    for token in forbidden:
        assert token not in workflow_text, (
            f"workflow must not run `{token}` — validators are stdlib-only"
        )


def test_h3_missing_logs_dir_is_handled(workflow_text):
    """AC4: empty / missing logs dir must succeed quietly."""
    # The implementation guards with `if [ -d survey-cli/logs ]`.
    assert "if [ -d survey-cli/logs ]" in workflow_text, (
        "workflow must guard validator calls against a missing survey-cli/logs/ directory"
    )


def test_h4_artifact_name_present(workflow_doc):
    """Sanity check: artifact has a `name:` so it's findable in the UI."""
    for job in (workflow_doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if step.get("uses", "").startswith("actions/upload-artifact@"):
                with_block = step.get("with") or {}
                assert with_block.get("name"), "upload-artifact step must set a `name:`"
                return
    pytest.fail("no upload-artifact step found")


def test_h5_workflow_name_is_schema_guard(workflow_doc):
    assert workflow_doc.get("name") == "schema-guard"
