from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def _as_round_dict(record: Any) -> dict[str, Any]:
    if is_dataclass(record):
        data = asdict(record)
    elif isinstance(record, dict):
        data = dict(record)
    else:
        data = {
            "round_number": getattr(record, "round_number", None),
            "commit": getattr(record, "commit", None),
            "perf_metric": getattr(record, "perf_metric", None),
            "perf_unit": getattr(record, "perf_unit", None),
            "judge_perf_metric": getattr(record, "judge_perf_metric", None),
            "judge_perf_name": getattr(record, "judge_perf_name", None),
            "judge_success_rate": getattr(record, "judge_success_rate", None),
            "passed": getattr(record, "passed", False),
            "global_objective_status": getattr(record, "global_objective_status", "unknown"),
            "global_objective_reason": getattr(record, "global_objective_reason", ""),
            "profile_skipped": getattr(record, "profile_skipped", False),
        }
    if "round" in data and "round_number" not in data:
        data["round_number"] = data["round"]
    return data


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def benchmark_contract(goal_contract: dict[str, Any] | None) -> dict[str, Any]:
    """Extract benchmark target metadata from a target ``goal.json`` dict."""
    if not isinstance(goal_contract, dict):
        return {}
    benchmark = goal_contract.get("benchmark") if isinstance(goal_contract.get("benchmark"), dict) else {}
    baseline = goal_contract.get("baseline") if isinstance(goal_contract.get("baseline"), dict) else {}
    baseline_metrics = (
        baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else {}
    )
    primary_metric = benchmark.get("primary_metric")
    baseline_value = _numeric(baseline_metrics.get(primary_metric)) if primary_metric else None
    return {
        "primary_metric": primary_metric,
        "higher_is_better": benchmark.get("higher_is_better", True),
        "baseline_engine": baseline.get("engine"),
        "baseline_metrics": baseline_metrics,
        "baseline_value": baseline_value,
        "benchmark_matrix": benchmark.get("benchmark_matrix"),
        "acceptance": goal_contract.get("acceptance") if isinstance(goal_contract.get("acceptance"), dict) else {},
    }


def summarize_rounds(
    records: list[Any],
    goal_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable monitor-friendly summary for agent-loop rounds."""
    contract = benchmark_contract(goal_contract)
    primary_metric = contract.get("primary_metric")
    baseline_value = contract.get("baseline_value")
    higher_is_better = bool(contract.get("higher_is_better", True))
    rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None

    for record in records:
        data = _as_round_dict(record)
        profiler_metric = _numeric(data.get("perf_metric"))
        judge_metric = _numeric(data.get("judge_perf_metric"))
        metric = judge_metric if judge_metric is not None else profiler_metric
        passed = bool(data.get("passed"))
        delta_pct = None
        if metric is not None and baseline_value:
            delta_pct = (metric / baseline_value - 1.0) * 100.0
        row = {
            "round": data.get("round_number"),
            "status": "passed" if passed else "failed",
            "global_objective_status": data.get("global_objective_status", "unknown"),
            "global_objective_reason": data.get("global_objective_reason", ""),
            "commit": data.get("commit"),
            "metric_name": data.get("judge_perf_name") or data.get("perf_unit") or primary_metric,
            "metric_value": metric,
            "metric_source": "judge" if judge_metric is not None else ("profiler" if profiler_metric is not None else None),
            "profiler_metric_value": profiler_metric,
            "judge_metric_value": judge_metric,
            "judge_success_rate": _numeric(data.get("judge_success_rate")),
            "baseline_value": baseline_value,
            "delta_pct": delta_pct,
            "profile_skipped": bool(data.get("profile_skipped")),
        }
        rows.append(row)
        if passed and metric is not None:
            best_value = best.get("metric_value") if best else None
            if best_value is None or (
                metric > best_value if higher_is_better else metric < best_value
            ):
                best = row

    latest = rows[-1] if rows else None
    return {
        "benchmark": contract,
        "rounds": rows,
        "best_round": best,
        "latest_round": latest,
        "global_objective_status": (
            latest.get("global_objective_status") if isinstance(latest, dict) else "unknown"
        ),
        "global_objective_reason": (
            latest.get("global_objective_reason") if isinstance(latest, dict) else ""
        ),
    }
