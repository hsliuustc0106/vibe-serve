from dataclasses import dataclass

import pytest

from vibe_serve.loops.agent.round_summary import benchmark_contract, summarize_rounds


@dataclass
class Round:
    round_number: int
    commit: str | None
    perf_metric: float | None
    perf_unit: str | None
    passed: bool
    profile_skipped: bool = False


def test_benchmark_contract_extracts_primary_baseline_metric():
    goal = {
        "benchmark": {"primary_metric": "tokens_per_sec", "higher_is_better": True},
        "baseline": {
            "engine": "vllm",
            "metrics": {"tokens_per_sec": 857.16, "p95_latency_ms": 370.0},
        },
    }

    contract = benchmark_contract(goal)

    assert contract["primary_metric"] == "tokens_per_sec"
    assert contract["baseline_engine"] == "vllm"
    assert contract["baseline_value"] == 857.16
    assert contract["baseline_metrics"]["p95_latency_ms"] == 370.0


def test_summarize_rounds_adds_delta_and_best_round():
    goal = {
        "benchmark": {"primary_metric": "tokens_per_sec"},
        "baseline": {"engine": "vllm", "metrics": {"tokens_per_sec": 100.0}},
    }
    records = [
        Round(1, "aaa", None, None, False),
        Round(2, "bbb", 80.0, "tokens_per_sec", True),
        Round(3, "ccc", 120.0, "tokens_per_sec", True),
    ]

    summary = summarize_rounds(records, goal)

    assert summary["rounds"][0]["status"] == "failed"
    assert summary["rounds"][1]["delta_pct"] == pytest.approx(-20.0)
    assert summary["rounds"][2]["delta_pct"] == pytest.approx(20.0)
    assert summary["best_round"]["round"] == 3
    assert summary["best_round"]["metric_value"] == 120.0


def test_summarize_rounds_handles_missing_goal_contract():
    summary = summarize_rounds([Round(1, "aaa", 42.0, "tok/s", True)], None)

    assert summary["benchmark"] == {}
    assert summary["rounds"][0]["baseline_value"] is None
    assert summary["rounds"][0]["delta_pct"] is None
    assert summary["best_round"]["round"] == 1


def test_summarize_rounds_respects_lower_is_better_metrics():
    goal = {
        "benchmark": {"primary_metric": "p95_latency_ms", "higher_is_better": False},
        "baseline": {"engine": "vllm", "metrics": {"p95_latency_ms": 100.0}},
    }
    records = [
        Round(1, "aaa", 120.0, "p95_latency_ms", True),
        Round(2, "bbb", 80.0, "p95_latency_ms", True),
    ]

    summary = summarize_rounds(records, goal)

    assert summary["best_round"]["round"] == 2
    assert summary["best_round"]["metric_value"] == 80.0
