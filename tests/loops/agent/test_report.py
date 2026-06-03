from __future__ import annotations

import json
from pathlib import Path

from vibe_serve.loops.agent.report import build_agent_report, load_report_data


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_run(tmp_path: Path) -> Path:
    exp_dir = tmp_path / "exp"
    workspace = exp_dir / "workspace"
    logs = exp_dir / "logs"
    workspace.mkdir(parents=True)
    logs.mkdir()
    _write_json(
        logs / "round_summary.json",
        {
            "benchmark": {
                "primary_metric": "tokens_per_sec",
                "baseline_engine": "vllm",
                "baseline_value": 100.0,
            },
            "rounds": [
                {
                    "round": 1,
                    "status": "failed",
                    "metric_name": "tokens_per_sec",
                    "metric_value": None,
                    "baseline_value": 100.0,
                    "delta_pct": None,
                    "commit": "aaa",
                },
                {
                    "round": 2,
                    "status": "passed",
                    "metric_name": "tokens_per_sec",
                    "metric_value": 120.0,
                    "baseline_value": 100.0,
                    "delta_pct": 20.0,
                    "commit": "bbb",
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
    _write_json(logs / "rounds.json", [{"round": 1, "passed": False}, {"round": 2, "passed": True}])
    _write_json(logs / "usage.json", {"implementer": {"tokens": 123}})
    (logs / "round002.log").write_text("raw log\n", encoding="utf-8")
    (workspace / "progress.md").write_text(
        "\n".join(
            [
                "# Progress",
                "",
                "## Round 1 — Orchestrator (plan)",
                "- **reasoning**: start with baseline",
                "",
                "## Round 1 — Implementer (attempt 1)",
                "### Summary",
                "Built the server.",
                "",
                "## Round 1 — Judge (attempt 1)",
                "- **verdict**: fail",
                "",
                "## Round 2 — Judge (attempt 1)",
                "- **verdict**: pass",
            ]
        ),
        encoding="utf-8",
    )
    return exp_dir


def test_load_report_data_reads_stable_artifacts(tmp_path: Path):
    exp_dir = _make_run(tmp_path)

    data = load_report_data(exp_dir)

    assert data["benchmark"]["baseline_engine"] == "vllm"
    assert data["rounds"][1]["metric_value"] == 120.0
    assert data["best_round"]["round"] == 2
    assert [event["agent"] for event in data["events"]] == [
        "Orchestrator",
        "Implementer",
        "Judge",
        "Judge",
    ]
    assert data["usage"][0]["file"] == "usage.json"
    assert "round002.log" in data["artifacts"]


def test_build_agent_report_writes_html_and_data(tmp_path: Path):
    exp_dir = _make_run(tmp_path)

    result = build_agent_report(exp_dir)

    html = result.report_path.read_text(encoding="utf-8")
    data = json.loads(result.data_path.read_text(encoding="utf-8"))
    assert "Agent Run Report" in html
    assert "Round Progress" in html
    assert "Metric (tok/s)" in html
    assert "Recent Agent Events" in html
    assert 'class="event implementer split"' in html
    assert "<summary>Recent Usage</summary>" in html
    assert "<summary>Benchmark Artifacts</summary>" in html
    assert "<details open>" not in html
    assert data["best_round"]["round"] == 2
