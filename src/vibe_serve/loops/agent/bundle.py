from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BundleResult:
    bundle_dir: Path
    manifest_path: Path
    round_number: int | None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_copy(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    if src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _select_round(summary: dict[str, Any], requested_round: int | None) -> dict[str, Any]:
    rounds = summary.get("rounds") if isinstance(summary.get("rounds"), list) else []
    if requested_round is not None:
        for row in rounds:
            if row.get("round") == requested_round:
                return row
        raise ValueError(f"round {requested_round} not found in round_summary.json")

    best = summary.get("best_round")
    if isinstance(best, dict) and best.get("round") is not None:
        return best

    passed = [row for row in rounds if row.get("status") == "passed"]
    if passed:
        return passed[-1]
    raise ValueError("no passed or best round found in round_summary.json")


def _artifact_candidates(log_dir: Path, round_number: int | None) -> list[Path]:
    patterns = [
        "round_summary.json",
        "rounds.json",
        "usage.json",
        "usage*.json",
        "benchmark*.json",
        "checker*.json",
        "accuracy*.json",
        "judge*.json",
    ]
    if round_number is not None:
        try:
            round_number_int = int(round_number)
            log_pattern = f"round{round_number_int:03d}*.log"
        except (TypeError, ValueError):
            log_pattern = f"round*{round_number}*.log"
        patterns.extend(
            [
                f"*round*{round_number}*benchmark*.json",
                f"*round*{round_number}*checker*.json",
                f"*round*{round_number}*accuracy*.json",
                log_pattern,
            ]
        )
    found: list[Path] = []
    for pattern in patterns:
        found.extend(log_dir.glob(pattern))
    return sorted({path for path in found if path.is_file()})


def build_accepted_round_bundle(
    exp_dir: Path,
    *,
    output_dir: Path | None = None,
    round_number: int | None = None,
    name: str | None = None,
) -> BundleResult:
    """Package a finished agent-loop run into a deployable accepted-round bundle."""
    exp_dir = exp_dir.expanduser().resolve()
    workspace = exp_dir / "workspace"
    log_dir = exp_dir / "logs"
    summary_path = log_dir / "round_summary.json"

    if not workspace.is_dir():
        raise FileNotFoundError(f"workspace not found: {workspace}")
    if not summary_path.is_file():
        raise FileNotFoundError(f"round summary not found: {summary_path}")

    summary = _read_json(summary_path)
    selected = _select_round(summary, round_number)
    selected_round = selected.get("round")
    suffix = name or (
        f"round-{selected_round}" if selected_round is not None else "accepted-round"
    )
    bundle_root = (output_dir or exp_dir / "bundles").expanduser().resolve()
    bundle_dir = bundle_root / suffix

    if bundle_dir.is_dir():
        shutil.rmtree(bundle_dir)
    elif bundle_dir.exists():
        bundle_dir.unlink()
    bundle_dir.mkdir(parents=True)

    _safe_copy(workspace, bundle_dir / "workspace")
    artifacts_dir = bundle_dir / "artifacts"
    artifacts_dir.mkdir()
    copied_artifacts: list[str] = []
    for artifact in _artifact_candidates(log_dir, selected_round):
        rel = artifact.relative_to(log_dir)
        target = artifacts_dir / rel
        _safe_copy(artifact, target)
        copied_artifacts.append(str(rel))

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "source_experiment": str(exp_dir),
        "selected_round": selected,
        "benchmark": summary.get("benchmark", {}),
        "best_round": summary.get("best_round"),
        "artifacts": copied_artifacts,
        "entrypoints": _detect_entrypoints(bundle_dir / "workspace"),
    }
    manifest_path = bundle_dir / "bundle.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_readme(bundle_dir, manifest)

    return BundleResult(
        bundle_dir=bundle_dir,
        manifest_path=manifest_path,
        round_number=selected_round if isinstance(selected_round, int) else None,
    )


def _detect_entrypoints(workspace: Path) -> dict[str, str]:
    entrypoints: dict[str, str] = {}
    for candidate in ("run_server.sh", "scripts/run_server.sh"):
        if (workspace / candidate).is_file():
            entrypoints["server"] = candidate
            break
    for candidate in ("run_checker.sh", "scripts/run_checker.sh"):
        if (workspace / candidate).is_file():
            entrypoints["checker"] = candidate
            break
    for candidate in ("run_benchmark.sh", "scripts/run_benchmark.sh"):
        if (workspace / candidate).is_file():
            entrypoints["benchmark"] = candidate
            break
    return entrypoints


def _write_readme(bundle_dir: Path, manifest: dict[str, Any]) -> None:
    selected = manifest.get("selected_round") or {}
    entrypoints = manifest.get("entrypoints") or {}
    round_val = selected.get("round")
    status_val = selected.get("status")
    metric_val = selected.get("metric_value")
    metric_name = selected.get("metric_name")
    baseline_val = selected.get("baseline_value")
    lines = [
        "# Accepted Round Bundle",
        "",
        f"- Round: {round_val if round_val is not None else 'unknown'}",
        f"- Status: {status_val if status_val is not None else 'unknown'}",
        f"- Metric: {metric_val if metric_val is not None else 'unknown'} {metric_name or ''}".rstrip(),
        f"- Baseline: {baseline_val if baseline_val is not None else 'unknown'}",
        "",
        "## Contents",
        "",
        "- `workspace/`: generated inference engine files for this accepted round.",
        "- `artifacts/`: copied logs, checker, benchmark, and summary JSON files.",
        "- `bundle.json`: machine-readable bundle manifest.",
        "",
    ]
    if entrypoints:
        lines.extend(["## Entrypoints", ""])
        for key, value in entrypoints.items():
            lines.append(f"- {key}: `workspace/{value}`")
        lines.append("")
    (bundle_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
