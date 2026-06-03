from pathlib import Path

import vibe_serve.loops.agent as agent_loop_pkg
from vibe_serve.prompts import render_template

TEMPLATE_DIR = Path(agent_loop_pkg.__file__).resolve().parent / "templates"


def test_implementer_prompt_mentions_starter_template():
    prompt = render_template(
        "implementer_prompt.j2",
        template_dir=TEMPLATE_DIR,
        reference_path="reference/reference.py",
        modality="text_generation",
        task="Build a server.",
        pass_criteria="/health passes.",
        retry=1,
        feedback=None,
        runtime_notes="",
        env_kind="local",
        goal_contract=None,
    )

    assert "starter_template/" in prompt
    assert "FastAPI + Hugging Face Transformers" in prompt
