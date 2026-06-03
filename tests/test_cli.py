"""Tests for the unified ``vibeserve`` CLI dispatcher."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe_serve import cli
from vibe_serve.cli import _extract_flag, _extract_loop_selection, _resolve_exp_dir, main

# ---------------------------------------------------------------------------
# Flag extraction
# ---------------------------------------------------------------------------


def test_extract_flag_space_form():
    val, rest = _extract_flag(["--outer-loop", "agent", "--ref", "x"], "--outer-loop")
    assert val == "agent"
    assert rest == ["--ref", "x"]


def test_extract_flag_equals_form():
    val, rest = _extract_flag(["--ref", "x", "--outer-loop=evolve"], "--outer-loop")
    assert val == "evolve"
    assert rest == ["--ref", "x"]


def test_extract_flag_missing_returns_none():
    val, rest = _extract_flag(["--ref", "x"], "--outer-loop")
    assert val is None
    assert rest == ["--ref", "x"]


def test_extract_flag_dangling_exits():
    with pytest.raises(SystemExit) as exc:
        _extract_flag(["--outer-loop"], "--outer-loop")
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# argv → loop kind
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv,expected_kind,expected_rest",
    [
        (["--outer-loop", "agent", "--ref", "x"], "agent", ["--ref", "x"]),
        (["--outer-loop", "plain", "--exp-name", "e"], "plain", ["--exp-name", "e"]),
        (["--outer-loop", "evolve", "--seed", "1"], "evolve", ["--seed", "1"]),
    ],
)
def test_extract_loop_selection(argv: list[str], expected_kind: str, expected_rest: list[str]):
    kind, rest = _extract_loop_selection(argv)
    assert kind == expected_kind
    assert rest == expected_rest


def test_extract_loop_selection_defaults_to_agent():
    kind, rest = _extract_loop_selection(["--ref", "x"])
    assert kind == "agent"
    assert rest == ["--ref", "x"]


def test_extract_loop_selection_unknown_outer_loop_exits():
    with pytest.raises(SystemExit) as exc:
        _extract_loop_selection(["--outer-loop", "nope"])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# main() routes to the right runner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "loop_name,runner_attr",
    [
        ("agent", "_run_agent"),
        ("evolve", "_run_evolve"),
        ("plain", "_run_plain"),
    ],
)
def test_main_routes_to_runner(loop_name: str, runner_attr: str):
    argv = ["vibe-serve", "--outer-loop", loop_name, "--exp-name", "x"]
    with patch.object(sys, "argv", argv), patch(
        f"vibe_serve.cli.{runner_attr}"
    ) as runner:
        main()
        runner.assert_called_once()
        args = runner.call_args.args[0]
        assert args.exp_name == "x"


def test_main_routes_bundle_command():
    argv = ["vibe-serve", "bundle", "--run-dir", "my-run", "--round", "2"]
    with patch.object(sys, "argv", argv), patch("vibe_serve.cli._run_bundle") as runner:
        main()
        runner.assert_called_once()
        args = runner.call_args.args[0]
        assert args.run_dir == "my-run"
        assert args.round == 2


def test_main_routes_report_command():
    argv = ["vibe-serve", "report", "--run-dir", "my-run", "--output", "report.html"]
    with patch.object(sys, "argv", argv), patch("vibe_serve.cli._run_report") as runner:
        main()
        runner.assert_called_once()
        args = runner.call_args.args[0]
        assert args.run_dir == "my-run"
        assert args.output == Path("report.html")


def test_resolve_exp_dir_latest_ignores_same_named_cwd_directory(tmp_path, monkeypatch):
    exp_env = tmp_path / "exp_env"
    latest = exp_env / "20260603-run"
    latest.mkdir(parents=True)
    (tmp_path / "20260603-run").mkdir()
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    assert _resolve_exp_dir("latest") == Path(tmp_path / "exp_env" / "20260603-run")
