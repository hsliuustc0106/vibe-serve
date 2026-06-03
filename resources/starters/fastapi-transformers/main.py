from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from threading import Thread
from typing import Any

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

MODEL_ID = os.getenv("MODEL_ID", "gpt2")
WEIGHTS_DIR = os.getenv("WEIGHTS_DIR", "/model")
HOSTED_MODEL_NAME = os.getenv("SERVED_MODEL_NAME", MODEL_ID)
DTYPE_NAME = os.getenv("TORCH_DTYPE", "auto")
DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
MAX_INPUT_TOKENS = int(os.getenv("MAX_INPUT_TOKENS", "4096"))


class CompletionRequest(BaseModel):
    model: str | None = None
    prompt: str | list[str]
    prediction: Any | None = None
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

        def _load_model() -> tuple[Any, Any]:
            tokenizer = AutoTokenizer.from_pretrained(source, trust_remote_code=True)
            if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
                tokenizer.pad_token = tokenizer.eos_token
            model = AutoModelForCausalLM.from_pretrained(
                source,
                torch_dtype=_torch_dtype(),
                trust_remote_code=True,
            )
            model.to(DEVICE)
            model.eval()
            return tokenizer, model

        _tokenizer, _model = await asyncio.to_thread(_load_model)


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


def _usage(prompt: str | int, completion: str) -> dict[str, int]:
    assert _tokenizer is not None
    if isinstance(prompt, int):
        prompt_tokens = prompt
    else:
        prompt_tokens = len(_tokenizer.encode(prompt, add_special_tokens=False))
    completion_tokens = len(_tokenizer.encode(completion, add_special_tokens=False))
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _completion_payload(prompt_tokens: int, text: str, finish_reason: str = "stop") -> dict[str, Any]:
    return {
        "id": f"cmpl-{uuid.uuid4().hex}",
        "object": "text_completion",
        "created": int(time.time()),
        "model": HOSTED_MODEL_NAME,
        "choices": [{"text": text, "index": 0, "finish_reason": finish_reason}],
        "usage": _usage(prompt_tokens, text),
    }


def _generation_inputs(req: CompletionRequest) -> tuple[int, dict[str, Any]]:
    assert _tokenizer is not None and _model is not None
    prompt = _prompt_text(req.prompt)
    encoded = _tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_INPUT_TOKENS,
    ).to(DEVICE)
    prompt_tokens = int(encoded["input_ids"].shape[-1])
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
    return prompt_tokens, generate_kwargs


def _generate_text(req: CompletionRequest) -> tuple[int, str]:
    assert _tokenizer is not None and _model is not None
    prompt_tokens, generate_kwargs = _generation_inputs(req)
    with torch.inference_mode():
        output = _model.generate(**generate_kwargs)
    generated_ids = output[0, generate_kwargs["input_ids"].shape[-1]:]
    text = _tokenizer.decode(generated_ids, skip_special_tokens=True)
    return prompt_tokens, _apply_stop(text, _stop_sequences(req.stop))


async def _stream_completion(req: CompletionRequest):
    completion_id = f"cmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    try:
        assert _tokenizer is not None and _model is not None
        prompt_tokens, generate_kwargs = _generation_inputs(req)
        streamer = TextIteratorStreamer(
            _tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        generate_kwargs["streamer"] = streamer
        text_parts: list[str] = []
        generation_error: list[BaseException] = []

        def _run_generate() -> None:
            try:
                with torch.inference_mode():
                    _model.generate(**generate_kwargs)
            except BaseException as exc:
                generation_error.append(exc)
                streamer.on_finalized_text("", stream_end=True)

        thread = Thread(target=_run_generate, daemon=True)
        thread.start()

        def _next_piece() -> str | None:
            return next(streamer, None)

        stop_sequences = _stop_sequences(req.stop)
        emitted_len = 0
        stopped = False
        while True:
            piece = await asyncio.to_thread(_next_piece)
            if piece is None:
                break
            if stopped:
                continue
            text_parts.append(piece)
            text = "".join(text_parts)
            stopped_text = _apply_stop(text, stop_sequences)
            emit = stopped_text[emitted_len:]
            emitted_len = len(stopped_text)
            if stopped_text != text:
                stopped = True
            if not emit:
                continue
            payload = {
                "id": completion_id,
                "object": "text_completion.chunk",
                "created": created,
                "model": HOSTED_MODEL_NAME,
                "choices": [{"text": emit, "index": 0, "finish_reason": None}],
            }
            yield f"data: {json.dumps(payload)}\n\n"
        thread.join()
        if generation_error:
            raise generation_error[0]
        text = _apply_stop("".join(text_parts), stop_sequences)
        final_payload = {
            "id": completion_id,
            "object": "text_completion.chunk",
            "created": created,
            "model": HOSTED_MODEL_NAME,
            "choices": [{"text": "", "index": 0, "finish_reason": "stop"}],
            "usage": _usage(prompt_tokens, text),
        }
        yield f"data: {json.dumps(final_payload)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as exc:
        error_payload = {
            "error": {
                "type": "inference_error",
                "message": str(exc),
            }
        }
        yield f"data: {json.dumps(error_payload)}\n\n"
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
        prompt_tokens, text = await asyncio.to_thread(_generate_text, req)
        return JSONResponse(_completion_payload(prompt_tokens, text))
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": {"type": "inference_error", "message": str(exc)}},
        )
