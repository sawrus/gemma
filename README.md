# Gemma Local Agent Runtime

Makefile-driven tooling for running Gemma 4 locally on Apple Silicon as an OpenAI-compatible server for Codex and opencode.

## Quick Start

Edit `.env` and set `HF_TOKEN` when Hugging Face requires authentication.

```sh
make install
make model-download
make serve
```

Default server URL:

```text
http://127.0.0.1:8080/v1
```

Use any non-empty local API key placeholder, for example `local`.

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

