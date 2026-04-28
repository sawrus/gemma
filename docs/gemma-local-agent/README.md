# Gemma 4 Local Agent Runtime

This project provides Makefile-driven scripts for running Gemma 4 locally on an Apple Silicon Mac mini as an OpenAI-compatible server for Codex and opencode.

## Configuration

Create `.env` from the committed template:

```sh
cp .env.example .env
```

Set `HF_TOKEN` when Hugging Face access requires authentication:

```dotenv
HF_TOKEN=hf_your_token_here
HF_HOME=.cache/huggingface
GEMMA_MODEL_ID=majentik/gemma-4-26B-A4B-it-TurboQuant-MLX-2bit
GEMMA_MODEL_ALIAS=gemma4-26b-a4b-it-tq-2bit
GEMMA_MODEL_DIR=.models/gemma4-26b-a4b-it-tq-2bit
GEMMA_HOST=127.0.0.1
GEMMA_PORT=8080
GEMMA_BACKEND_PORT=18080
GEMMA_BACKEND_MODULE=mlx_lm.server
GEMMA_KV_BITS=3.5
GEMMA_KV_QUANT_SCHEME=turboquant
```

`.env` is ignored by git. Scripts pass `HF_TOKEN` to Hugging Face download calls but do not print it.

## Usage

```sh
make install
make model-download
make model-repair
make serve
```

`make model-download` writes `manifest.json` after the Hugging Face snapshot is
complete. `make serve` requires that manifest and will fail fast when the local
model is missing, so a request to opencode cannot accidentally trigger another
download.

By default `make serve` starts two local HTTP services:

- public OpenAI-compatible alias proxy: `http://127.0.0.1:8080/v1`
- internal raw `mlx_lm.server` backend: `http://127.0.0.1:18080/v1`

The proxy exposes `GEMMA_MODEL_ALIAS` to clients and rewrites that alias to the
local absolute model path before forwarding to the MLX backend.

For the 2-bit TurboQuant profile, run `make model-repair` once after download.
It backs up `config.json` to `config.json.bak` and corrects the top-level
`quantization.bits` metadata when the model files are 2-bit but config metadata
claims 4-bit. `make serve` also applies this repair automatically before start.

If you intentionally want lazy remote loading from Hugging Face, run:

```sh
python scripts/serve_openai.py --allow-remote-model
```

The local OpenAI-compatible base URL is:

```text
http://127.0.0.1:8080/v1
```

Use any non-empty API key placeholder such as `local`.

## opencode Provider

opencode can use this server as a custom OpenAI-compatible provider.

1. Start the local server:

   ```sh
   make serve
   ```

2. In opencode, run `/connect`, choose `Other`, set provider id to `gemma-local`,
   and enter any non-empty API key placeholder, for example `local`.

3. Add this provider configuration to `.opencode/opencode.json` or your global
   `~/.config/opencode/opencode.json`:

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

If you edit the project `.opencode/opencode.json`, merge the `provider`, `model`,
and `small_model` keys with the existing agent workflow config instead of replacing
the whole file.

The model id in opencode should be the alias from `GEMMA_MODEL_ALIAS`, not the
Hugging Face id. The alias proxy maps it to the local path. Use this command to
inspect the backend path and public alias:

```sh
python scripts/serve_openai.py --print-command
```

## Benchmarking

Start the server, then run:

```sh
make benchmark
```

Reports are written to `reports/benchmarks/` as JSON and Markdown.

## Tests

Default checks do not download the real model:

```sh
make lint
make test
make test-e2e
```

Real hardware checks are explicit:

```sh
make test-real
make benchmark-real
```

These require network access, enough disk space, and enough unified memory for the configured model.
