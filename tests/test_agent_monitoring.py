from __future__ import annotations

from vibe_serve.loops.agent.loop import (
    _extract_judge_benchmark_metrics,
    _global_objective_status,
)
from vibe_serve.loops.agent.report import render_report_html
from vibe_serve.loops.agent.round_summary import summarize_rounds
from vibe_serve.schemas import JudgeResponse, Verdict


GOAL_CONTRACT = {
    "benchmark": {
        "primary_metric": "tokens_per_sec",
        "higher_is_better": True,
    },
    "acceptance": {
        "success_rate": 1.0,
    },
}


def test_extract_judge_metric_prefers_observed_value_over_threshold() -> None:
    verdict = JudgeResponse(
        analysis=(
            "Full benchmark succeeded with success_rate was 1.0. "
            "Required `tokens_per_sec >= 84.3565`, but observed `58.057` "
            "for concurrency=1."
        ),
        feedback="Performance gate fail.",
        verdict=Verdict.FAIL,
    )

    metric, metric_name, success_rate = _extract_judge_benchmark_metrics(
        verdict,
        GOAL_CONTRACT,
    )

    assert metric_name == "tokens_per_sec"
    assert metric == 58.057
    assert success_rate == 1.0


def test_extract_judge_metric_accepts_observed_value_before_metric_name() -> None:
    verdict = JudgeResponse(
        analysis=(
            "Full benchmark target failed: observed `62.049` for "
            "`tokens_per_sec` with success_rate = 1.0."
        ),
        feedback="Performance gate fail.",
        verdict=Verdict.FAIL,
    )

    metric, metric_name, success_rate = _extract_judge_benchmark_metrics(
        verdict,
        GOAL_CONTRACT,
    )

    assert metric_name == "tokens_per_sec"
    assert metric == 62.049
    assert success_rate == 1.0


def test_round_summary_prefers_judge_metric_and_records_global_status() -> None:
    records = [
        {
            "round": 1,
            "commit": "abc123",
            "perf_metric": 84.3565,
            "perf_unit": "tokens_per_sec",
            "judge_perf_metric": 62.049,
            "judge_perf_name": "tokens_per_sec",
            "judge_success_rate": 1.0,
            "passed": False,
            "global_objective_status": "failed",
            "global_objective_reason": "performance gate failed",
            "profile_skipped": True,
        }
    ]

    summary = summarize_rounds(records, GOAL_CONTRACT)
    row = summary["rounds"][0]

    assert row["metric_value"] == 62.049
    assert row["metric_source"] == "judge"
    assert row["profiler_metric_value"] == 84.3565
    assert row["judge_success_rate"] == 1.0
    assert row["global_objective_status"] == "failed"
    assert summary["global_objective_status"] == "failed"


def test_global_objective_status_separates_round_pass_from_regression() -> None:
    prior = [
        {
            "round": 1,
            "commit": "abc123",
            "judge_perf_metric": 84.3565,
            "judge_perf_name": "tokens_per_sec",
            "passed": True,
            "profile_skipped": True,
        }
    ]

    status, reason = _global_objective_status(
        passed=True,
        judge_perf_metric=62.049,
        judge_perf_name="tokens_per_sec",
        judge_success_rate=1.0,
        records=prior,
        goal_contract_data=GOAL_CONTRACT,
    )

    assert status == "regressed"
    assert "trails best round 1" in reason


def test_global_objective_failure_reason_keeps_measured_metrics() -> None:
    status, reason = _global_objective_status(
        passed=False,
        judge_perf_metric=62.049,
        judge_perf_name="tokens_per_sec",
        judge_success_rate=1.0,
        records=[],
        goal_contract_data=GOAL_CONTRACT,
    )

    assert status == "failed"
    assert "judge verdict failed" in reason
    assert "tokens_per_sec=62.049" in reason
    assert "success_rate=1" in reason


def test_report_global_status_falls_back_to_latest_round() -> None:
    html = render_report_html(
        {
            "source_experiment": "/tmp/run",
            "benchmark": {"primary_metric": "tokens_per_sec"},
            "best_round": None,
            "rounds": [
                {
                    "round": 1,
                    "status": "failed",
                    "global_objective_status": "failed",
                    "global_objective_reason": "judge verdict failed; tokens_per_sec=62.049",
                    "metric_name": "tokens_per_sec",
                    "metric_value": 62.049,
                    "metric_source": "judge",
                }
            ],
            "events": [],
            "usage": [],
            "artifacts": [],
        }
    )

    assert "Latest Global" in html
    assert "failed" in html
    assert "judge verdict failed; tokens_per_sec=62.049" in html
