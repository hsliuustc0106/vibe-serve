import json

from vibe_serve.loops.agent.goal_contract import (
    find_goal_contract_path,
    load_goal_contract_text,
)


def test_finds_goal_contract_from_reference_dir(tmp_path):
    target = tmp_path / "target"
    ref = target / "reference"
    ref.mkdir(parents=True)
    goal = target / "goal.json"
    goal.write_text('{"name": "demo"}', encoding="utf-8")

    assert find_goal_contract_path(str(ref)) == goal


def test_finds_goal_contract_from_checker_or_bench_dir(tmp_path):
    target = tmp_path / "target"
    checker = target / "accuracy_checker"
    bench = target / "benchmark"
    checker.mkdir(parents=True)
    bench.mkdir()
    goal = target / "goal.json"
    goal.write_text('{"name": "demo"}', encoding="utf-8")

    assert find_goal_contract_path(str(target / "missing_ref"), str(checker), str(bench)) == goal


def test_load_goal_contract_formats_json(tmp_path):
    target = tmp_path / "target"
    ref = target / "reference"
    ref.mkdir(parents=True)
    (target / "goal.json").write_text('{"z": 1, "a": 2}', encoding="utf-8")

    path, text = load_goal_contract_text(str(ref))

    assert path == target / "goal.json"
    assert json.loads(text) == {"z": 1, "a": 2}
    assert text.splitlines()[1].startswith('  "a"')
