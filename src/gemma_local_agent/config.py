from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL_ID = "majentik/gemma-4-26B-A4B-it-TurboQuant-MLX-2bit"
DEFAULT_MODEL_ALIAS = "gemma4-26b-a4b-it-tq-2bit"
DEFAULT_MODEL_DIR = ".models/gemma4-26b-a4b-it-tq-2bit"
SECRET_KEYS = {"HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"}


@dataclass(frozen=True)
class Settings:
    hf_token: str
    hf_home: str
    model_id: str
    model_alias: str
    model_dir: Path
    host: str
    port: int
    backend_port: int
    backend_module: str
    kv_bits: str
    kv_quant_scheme: str

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    try:
        from dotenv import load_dotenv
    except ImportError:
        for key, value in parse_env_file(env_path).items():
            os.environ.setdefault(key, value)
        return
    load_dotenv(env_path, override=False)


def settings_from_env(env_file: str | Path = ".env") -> Settings:
    load_env_file(env_file)
    model_dir = Path(os.environ.get("GEMMA_MODEL_DIR", DEFAULT_MODEL_DIR)).expanduser()
    return Settings(
        hf_token=os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN", ""),
        hf_home=os.environ.get("HF_HOME", ".cache/huggingface"),
        model_id=os.environ.get("GEMMA_MODEL_ID", DEFAULT_MODEL_ID),
        model_alias=os.environ.get("GEMMA_MODEL_ALIAS", DEFAULT_MODEL_ALIAS),
        model_dir=model_dir,
        host=os.environ.get("GEMMA_HOST", "127.0.0.1"),
        port=int(os.environ.get("GEMMA_PORT", "8080")),
        backend_port=int(os.environ.get("GEMMA_BACKEND_PORT", "18080")),
        backend_module=os.environ.get("GEMMA_BACKEND_MODULE", "mlx_lm.server"),
        kv_bits=os.environ.get("GEMMA_KV_BITS", "3.5"),
        kv_quant_scheme=os.environ.get("GEMMA_KV_QUANT_SCHEME", "turboquant"),
    )


def redact_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def redact_mapping(values: dict[str, str]) -> dict[str, str]:
    return {
        key: redact_value(value) if key in SECRET_KEYS else value
        for key, value in values.items()
    }
