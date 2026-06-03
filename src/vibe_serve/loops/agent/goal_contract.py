from __future__ import annotations

import json
from pathlib import Path


def find_goal_contract_path(
    reference_path: str,
    acc_checker: str | None = None,
    bench: str | None = None,
) -> Path | None:
    """Find a target-level ``goal.json`` next to the run input bundle.

    Examples conventionally live under ``examples/<target>/`` with
    ``reference/``, ``accuracy_checker/``, and ``benchmark/`` subdirectories.
    The contract is target metadata, not a checker/benchmark implementation, so
    it belongs at that shared parent. This helper intentionally discovers the
    file from any provided artifact path so existing CLI invocations do not need
    a new flag.
    """
    candidates: list[Path] = []
    for raw in (reference_path, acc_checker, bench):
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if path.is_file():
            candidates.append(path.parent / "goal.json")
            candidates.append(path.parent.parent / "goal.json")
        else:
            candidates.append(path / "goal.json")
            candidates.append(path.parent / "goal.json")

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return None


def load_goal_contract_text(
    reference_path: str,
    acc_checker: str | None = None,
    bench: str | None = None,
) -> tuple[Path | None, str | None]:
    path = find_goal_contract_path(reference_path, acc_checker, bench)
    if path is None:
        return None, None
    text = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return path, text
    return path, json.dumps(parsed, indent=2, sort_keys=True)
