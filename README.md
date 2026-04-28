# Gemma Local Agent Runtime

Makefile-driven tooling for running Gemma 4 locally on Apple Silicon as an OpenAI-compatible server for Codex and opencode.

## Quick Start

Edit `.env` and set `HF_TOKEN` when Hugging Face requires authentication.

```sh
make install
make model-download
make serve
```

`make serve` requires a completed local download and checks for
`.models/gemma4-26b-a4b-it-tq-2bit/manifest.json`. It will fail fast instead
of letting the backend download the model on the first request. Lazy remote
loading is available only through `python scripts/serve_openai.py --allow-remote-model`.
By default it exposes a short public model alias through an OpenAI-compatible
proxy and keeps the raw `mlx_lm.server` backend on `GEMMA_BACKEND_PORT`.

Default server URL:

```text
http://127.0.0.1:8080/v1
```

Use any non-empty local API key placeholder, for example `local`.

## opencode Custom Provider

Start the local server first:

```sh
make serve
```

Then add a credential in opencode with `/connect`, choose `Other`, use provider id
`gemma-local`, and enter any non-empty key such as `local`.

Add or merge this provider block into your opencode config:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "gemma-local/gemma4-26b-a4b-it-tq-2bit",
  "small_model": "gemma-local/gemma4-26b-a4b-it-tq-2bit",
  "provider": {
    "gemma-local": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Gemma 4 26B TurboQuant (local)",
      "options": {
        "baseURL": "http://127.0.0.1:8080/v1"
      },
      "models": {
        "gemma4-26b-a4b-it-tq-2bit": {
          "name": "Gemma 4 26B A4B TurboQuant 2-bit local"
        }
      }
    }
  }
}
```

The public model name is `GEMMA_MODEL_ALIAS` from `.env`. The alias proxy maps
that name to the local absolute path before forwarding requests to `mlx-vlm`, so
opencode does not need to know the filesystem path. Sending the Hugging Face id
directly to a raw MLX backend would trigger another download.

This repository already has an `.opencode/opencode.json` for agent workflow settings.
Merge the `provider`, `model`, and `small_model` keys into that file or into your
global `~/.config/opencode/opencode.json`.

## Commands

```sh
make help
make benchmark
make lint
make test
make test-e2e
```

Real model checks are explicit because they download and load the model:

```sh
make test-real
make benchmark-real
```

See [docs/gemma-local-agent/README.md](docs/gemma-local-agent/README.md) for configuration details.
