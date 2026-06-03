from __future__ import annotations

from vibe_serve.context import _RunContext


def test_copy_benchmark_runner_seeds_workspace_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    starter = project_root / "resources" / "starters" / "fastapi-transformers"
    starter.mkdir(parents=True)
    runner = starter / "run_benchmark.sh"
    runner.write_text("#!/usr/bin/env bash\necho benchmark\n", encoding="utf-8")
    runner.chmod(0o755)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ctx = object.__new__(_RunContext)
    ctx.workspace = workspace
    monkeypatch.setattr("vibe_serve.context.PROJECT_ROOT", project_root)

    ctx._copy_benchmark_runner()

    copied = workspace / "run_benchmark.sh"
    assert copied.read_text(encoding="utf-8") == "#!/usr/bin/env bash\necho benchmark\n"


def test_copy_benchmark_runner_respects_existing_file(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    starter = project_root / "resources" / "starters" / "fastapi-transformers"
    starter.mkdir(parents=True)
    (starter / "run_benchmark.sh").write_text("new\n", encoding="utf-8")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    copied = workspace / "run_benchmark.sh"
    copied.write_text("custom\n", encoding="utf-8")

    ctx = object.__new__(_RunContext)
    ctx.workspace = workspace
    monkeypatch.setattr("vibe_serve.context.PROJECT_ROOT", project_root)

    ctx._copy_benchmark_runner(skip_if_present=True)

    assert copied.read_text(encoding="utf-8") == "custom\n"
