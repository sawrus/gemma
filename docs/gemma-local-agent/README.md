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
GEMMA_MODEL_DIR=.models/gemma4-26b-a4b-it-tq-2bit
GEMMA_HOST=127.0.0.1
GEMMA_PORT=8080
GEMMA_KV_BITS=3.5
GEMMA_KV_QUANT_SCHEME=turboquant
```

`.env` is ignored by git. Scripts pass `HF_TOKEN` to Hugging Face download calls but do not print it.

## Usage

```sh
make install
make model-download
make serve
```

The local OpenAI-compatible base URL is:

```text
http://127.0.0.1:8080/v1
```

Use any non-empty API key placeholder such as `local`.

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

