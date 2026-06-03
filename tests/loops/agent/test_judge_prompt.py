from pathlib import Path

from vibe_serve.prompts import render_template


TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "src" / "vibe_serve" / "loops" / "agent" / "templates"


def test_judge_prompt_orders_staged_validation_gates():
    prompt = render_template(
        "judge_prompt.j2",
        template_dir=TEMPLATE_DIR,
        objective="Objective",
        pass_criteria="Pass criteria",
        runtime_notes="",
        bench_path="bench",
        accuracy_checker_path="acc_checker",
        modality="text_generation",
    )

    expected = [
        "Unit tests",
        "Server startup",
        "Health check",
        "Single-request smoke",
        "Benchmark sanity",
        "Accuracy checker subset",
        "Accuracy checker",
        "Full benchmark only after correctness gates pass",
        "Cleanup",
    ]
    positions = [prompt.index(item) for item in expected]
    assert positions == sorted(positions)
    assert "Stop at the first hard failure" in prompt
