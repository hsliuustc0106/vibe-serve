from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibe_serve.loops.agent.bundle import build_accepted_round_bundle


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_build_bundle_uses_best_round_and_copies_workspace_artifacts(tmp_path: Path):
    exp_dir = tmp_path / "exp"
    workspace = exp_dir / "workspace"
    logs = exp_dir / "logs"
    workspace.mkdir(parents=True)
    logs.mkdir()
    (workspace / "main.py").write_text("print('server')\n", encoding="utf-8")
    (workspace / "scripts").mkdir()
    (workspace / "scripts" / "run_server.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    _write_json(
        logs / "round_summary.json",
        {
            "benchmark": {
                "primary_metric": "tokens_per_sec",
                "baseline_engine": "vllm",
                "baseline_value": 100.0,
            },
            "rounds": [
                {"round": 1, "status": "failed"},
                {
                    "round": 2,
                    "status": "passed",
                    "metric_name": "tokens_per_sec",
                    "metric_value": 120.0,
                    "baseline_value": 100.0,
                },
            ],
            "best_round": {
                "round": 2,
                "status": "passed",
                "metric_name": "tokens_per_sec",
                "metric_value": 120.0,
                "baseline_value": 100.0,
            },
        },
    )
    _write_json(logs / "rounds.json", [{"round": 2, "passed": True}])
    _write_json(logs / "benchmark-result.json", {"tokens_per_sec": 120.0})
    (logs / "round002.log").write_text("judge pass\n", encoding="utf-8")

    result = build_accepted_round_bundle(exp_dir)

    assert result.round_number == 2
    assert (result.bundle_dir / "workspace" / "main.py").is_file()
    assert (result.bundle_dir / "artifacts" / "round_summary.json").is_file()
    assert (result.bundle_dir / "artifacts" / "benchmark-result.json").is_file()
    assert (result.bundle_dir / "artifacts" / "round002.log").is_file()
    assert (result.bundle_dir / "README.md").is_file()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["selected_round"]["round"] == 2
    assert manifest["entrypoints"]["server"] == "scripts/run_server.sh"


def test_build_bundle_can_package_explicit_round(tmp_path: Path):
    exp_dir = tmp_path / "exp"
    (exp_dir / "workspace").mkdir(parents=True)
    _write_json(
        exp_dir / "logs" / "round_summary.json",
        {
            "rounds": [
                {"round": 1, "status": "passed", "metric_value": 90.0},
                {"round": 2, "status": "passed", "metric_value": 120.0},
            ],
            "best_round": {"round": 2, "status": "passed", "metric_value": 120.0},
        },
    )

    result = build_accepted_round_bundle(exp_dir, round_number=1, name="candidate")

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.bundle_dir.name == "candidate"
    assert manifest["selected_round"]["round"] == 1


def test_build_bundle_requires_an_accepted_round(tmp_path: Path):
    exp_dir = tmp_path / "exp"
    (exp_dir / "workspace").mkdir(parents=True)
    _write_json(
        exp_dir / "logs" / "round_summary.json",
        {"rounds": [{"round": 1, "status": "failed"}], "best_round": None},
    )

    with pytest.raises(ValueError, match="no passed or best round"):
        build_accepted_round_bundle(exp_dir)


def test_build_bundle_replaces_existing_file_bundle_path(tmp_path: Path):
    exp_dir = tmp_path / "exp"
    (exp_dir / "workspace").mkdir(parents=True)
    _write_json(
        exp_dir / "logs" / "round_summary.json",
        {
            "rounds": [{"round": 1, "status": "passed", "metric_value": 90.0}],
            "best_round": {"round": 1, "status": "passed", "metric_value": 90.0},
        },
    )
    bundle_path = exp_dir / "bundles" / "round-1"
    bundle_path.parent.mkdir()
    bundle_path.write_text("stale file\n", encoding="utf-8")

    result = build_accepted_round_bundle(exp_dir)

    assert result.bundle_dir.is_dir()
    assert result.manifest_path.is_file()


def test_build_bundle_replaces_existing_workspace_file_with_directory(tmp_path: Path):
    exp_dir = tmp_path / "exp"
    workspace = exp_dir / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "main.py").write_text("print('server')\n", encoding="utf-8")
    _write_json(
        exp_dir / "logs" / "round_summary.json",
        {
            "rounds": [{"round": 1, "status": "passed", "metric_value": 90.0}],
            "best_round": {"round": 1, "status": "passed", "metric_value": 90.0},
        },
    )
    output_dir = tmp_path / "out"
    stale_workspace = output_dir / "round-1" / "workspace"
    stale_workspace.parent.mkdir(parents=True)
    stale_workspace.write_text("stale file\n", encoding="utf-8")

    result = build_accepted_round_bundle(exp_dir, output_dir=output_dir)

    assert (result.bundle_dir / "workspace" / "main.py").is_file()


def test_build_bundle_readme_uses_unknown_for_none_values(tmp_path: Path):
    exp_dir = tmp_path / "exp"
    (exp_dir / "workspace").mkdir(parents=True)
    _write_json(
        exp_dir / "logs" / "round_summary.json",
        {
            "rounds": [
                {
                    "round": 1,
                    "status": "passed",
                    "metric_name": None,
                    "metric_value": None,
                    "baseline_value": None,
                }
            ],
            "best_round": {
                "round": 1,
                "status": "passed",
                "metric_name": None,
                "metric_value": None,
                "baseline_value": None,
            },
        },
    )

    result = build_accepted_round_bundle(exp_dir)

    readme = (result.bundle_dir / "README.md").read_text(encoding="utf-8")
    assert "- Metric: unknown" in readme
    assert "- Baseline: unknown" in readme
    assert "None" not in readme
