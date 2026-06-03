from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import Any

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_ID = os.getenv("MODEL_ID", "gpt2")
WEIGHTS_DIR = os.getenv("WEIGHTS_DIR", "/model")
HOSTED_MODEL_NAME = os.getenv("SERVED_MODEL_NAME", MODEL_ID)
DTYPE_NAME = os.getenv("TORCH_DTYPE", "auto")
DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
MAX_INPUT_TOKENS = int(os.getenv("MAX_INPUT_TOKENS", "4096"))


class CompletionRequest(BaseModel):
    model: str | None = None
    prompt: str | list[str]
    max_tokens: int = Field(default=128, ge=1)
    temperature: float = Field(default=0.0, ge=0.0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)
    stream: bool = False
    stop: str | list[str] | None = None
    prompt_is_preformatted: bool = False


app = FastAPI()
_tokenizer: Any | None = None
_model: Any | None = None
_load_lock = asyncio.Lock()


def _model_source() -> str:
    return WEIGHTS_DIR if os.path.exists(WEIGHTS_DIR) else MODEL_ID


def _torch_dtype() -> str | torch.dtype:
    if DTYPE_NAME == "auto":
        return "auto"
    if DTYPE_NAME in {"float16", "fp16"}:
        return torch.float16
    if DTYPE_NAME in {"bfloat16", "bf16"}:
        return torch.bfloat16
    if DTYPE_NAME in {"float32", "fp32"}:
        return torch.float32
    raise ValueError(f"Unsupported TORCH_DTYPE={DTYPE_NAME!r}")


async def _ensure_loaded() -> None:
    global _tokenizer, _model
    if _tokenizer is not None and _model is not None:
        return
    async with _load_lock:
        if _tokenizer is not None and _model is not None:
            return
        source = _model_source()
        _tokenizer = AutoTokenizer.from_pretrained(source, trust_remote_code=True)
        if _tokenizer.pad_token_id is None and _tokenizer.eos_token_id is not None:
            _tokenizer.pad_token = _tokenizer.eos_token
        _model = AutoModelForCausalLM.from_pretrained(
            source,
            torch_dtype=_torch_dtype(),
            trust_remote_code=True,
        )
        _model.to(DEVICE)
        _model.eval()


def _prompt_text(prompt: str | list[str]) -> str:
    if isinstance(prompt, list):
        return "\n".join(str(part) for part in prompt)
    return str(prompt)


def _stop_sequences(stop: str | list[str] | None) -> list[str]:
    if stop is None:
        return []
    if isinstance(stop, str):
        return [stop]
    return [str(item) for item in stop]


def _apply_stop(text: str, stops: list[str]) -> str:
    cut = len(text)
    for stop in stops:
        if not stop:
            continue
        idx = text.find(stop)
        if idx >= 0:
            cut = min(cut, idx)
    return text[:cut]


def _usage(prompt: str, completion: str) -> dict[str, int]:
    assert _tokenizer is not None
    prompt_tokens = len(_tokenizer.encode(prompt, add_special_tokens=False))
    completion_tokens = len(_tokenizer.encode(completion, add_special_tokens=False))
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _completion_payload(prompt: str, text: str, finish_reason: str = "stop") -> dict[str, Any]:
    return {
        "id": f"cmpl-{uuid.uuid4().hex}",
        "object": "text_completion",
        "created": int(time.time()),
        "model": HOSTED_MODEL_NAME,
        "choices": [{"text": text, "index": 0, "finish_reason": finish_reason}],
        "usage": _usage(prompt, text),
    }


def _generate_text(req: CompletionRequest) -> tuple[str, str]:
    assert _tokenizer is not None and _model is not None
    prompt = _prompt_text(req.prompt)
    encoded = _tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_INPUT_TOKENS,
    )
    encoded = {key: value.to(DEVICE) for key, value in encoded.items()}
    do_sample = req.temperature > 0
    generate_kwargs: dict[str, Any] = {
        **encoded,
        "max_new_tokens": req.max_tokens,
        "do_sample": do_sample,
        "pad_token_id": _tokenizer.pad_token_id,
        "eos_token_id": _tokenizer.eos_token_id,
    }
    if do_sample:
        generate_kwargs["temperature"] = req.temperature
        generate_kwargs["top_p"] = req.top_p
    with torch.inference_mode():
        output = _model.generate(**generate_kwargs)
    generated_ids = output[0, encoded["input_ids"].shape[-1]:]
    text = _tokenizer.decode(generated_ids, skip_special_tokens=True)
    return prompt, _apply_stop(text, _stop_sequences(req.stop))


async def _stream_completion(req: CompletionRequest):
    prompt, text = await asyncio.to_thread(_generate_text, req)
    for piece in text.splitlines(keepends=True) or [text]:
        payload = {
            "id": f"cmpl-{uuid.uuid4().hex}",
            "object": "text_completion.chunk",
            "created": int(time.time()),
            "model": HOSTED_MODEL_NAME,
            "choices": [{"text": piece, "index": 0, "finish_reason": None}],
        }
        yield f"data: {json.dumps(payload)}\n\n"
    final_payload = {
        "id": f"cmpl-{uuid.uuid4().hex}",
        "object": "text_completion.chunk",
        "created": int(time.time()),
        "model": HOSTED_MODEL_NAME,
        "choices": [{"text": "", "index": 0, "finish_reason": "stop"}],
        "usage": _usage(prompt, text),
    }
    yield f"data: {json.dumps(final_payload)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models")
async def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": HOSTED_MODEL_NAME,
                "object": "model",
                "created": 0,
                "owned_by": "local",
            }
        ],
    }


@app.post("/v1/completions")
async def completions(request: Request):
    try:
        body = await request.json()
        if "max_new_tokens" in body and "max_tokens" not in body:
            body["max_tokens"] = body["max_new_tokens"]
        req = CompletionRequest(**body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        await _ensure_loaded()
        if req.stream:
            return StreamingResponse(_stream_completion(req), media_type="text/event-stream")
        prompt, text = await asyncio.to_thread(_generate_text, req)
        return JSONResponse(_completion_payload(prompt, text))
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": {"type": "inference_error", "message": str(exc)}},
        )
