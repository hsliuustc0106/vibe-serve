# Reference model

`reference/meta.json` points to `Qwen/Qwen3-0.6B` on Hugging Face Hub.
The run harness will download this snapshot when needed.

If your workspace has local weights mounted, you can override by setting `VLLM_MODEL`
or the target `MODEL_ID` to a local path before starting your own server.

