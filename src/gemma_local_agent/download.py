from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gemma_local_agent.config import (
    DEFAULT_MODEL_DIR,
    DEFAULT_MODEL_ID,
    Settings,
    settings_from_env,
)
from gemma_local_agent.model_repair import repair_model_config
from gemma_local_agent.profiles import memory_guard, platform_guard, select_profile

SnapshotDownload = Callable[..., str]


@dataclass(frozen=True)
class DownloadOptions:
    settings: Settings
    profile_name: str | None = None
    revision: str | None = None
    force: bool = False


def directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def create_manifest(
    model_dir: Path,
    *,
    model_id: str,
    profile_name: str,
    revision: str | None,
) -> Path:
    files = [
        file
        for file in model_dir.rglob("*")
        if file.is_file() and file.name != "manifest.json"
    ]
    manifest = {
        "model_id": model_id,
        "profile": profile_name,
        "revision": revision or "default",
        "downloaded_at": datetime.now(UTC).isoformat(),
        "file_count": len(files),
        "size_bytes": sum(file.stat().st_size for file in files),
    }
    manifest_path = model_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def import_snapshot_download() -> SnapshotDownload:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is not installed. Run `make install` before downloading the model."
        ) from exc
    return snapshot_download


def validate_download_environment(options: DownloadOptions) -> list[str]:
    profile = select_profile(options.profile_name)
    messages: list[str] = []
    for result in (
        platform_guard(force=options.force),
        memory_guard(profile, force=options.force),
    ):
        messages.extend(result.messages)
        if not result.allowed:
            raise RuntimeError(result.messages[0])
    return messages


def download_model(
    options: DownloadOptions,
    *,
    snapshot_download_func: SnapshotDownload | None = None,
) -> Path:
    profile = select_profile(options.profile_name)
    validate_download_environment(options)
    snapshot = snapshot_download_func or import_snapshot_download()

    if options.profile_name and options.settings.model_id == DEFAULT_MODEL_ID:
        model_id = profile.model_id
    else:
        model_id = options.settings.model_id or profile.model_id

    if options.profile_name and str(options.settings.model_dir) == DEFAULT_MODEL_DIR:
        model_dir = Path(profile.model_dir)
    else:
        model_dir = options.settings.model_dir
    model_dir.mkdir(parents=True, exist_ok=True)

    if options.settings.hf_home:
        os.environ.setdefault("HF_HOME", options.settings.hf_home)

    snapshot(
        repo_id=model_id,
        revision=options.revision,
        local_dir=str(model_dir),
        token=options.settings.hf_token or None,
    )
    repair_model_config(
        model_dir,
        quant_bits=2 if profile.name == "26b-a4b-tq-2bit" else None,
    )
    return create_manifest(
        model_dir,
        model_id=model_id,
        profile_name=profile.name,
        revision=options.revision,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download Gemma 4 model from Hugging Face.")
    parser.add_argument("--env-file", default=".env", help="Path to env file.")
    parser.add_argument("--profile", default=None, help="Model profile name.")
    parser.add_argument("--revision", default=None, help="Optional Hugging Face revision.")
    parser.add_argument("--force", action="store_true", help="Bypass platform and memory guards.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from_env(args.env_file)
    options = DownloadOptions(
        settings=settings,
        profile_name=args.profile,
        revision=args.revision,
        force=args.force,
    )
    manifest = download_model(options)
    print(f"model downloaded; manifest written to {manifest}")
    return 0


def manifest_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
