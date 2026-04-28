from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from gemma_local_agent.config import Settings, settings_from_env


@dataclass(frozen=True)
class RepairResult:
    changed: bool
    message: str


def expected_bits(settings: Settings) -> int | None:
    marker = " ".join(
        [
            settings.model_id.lower(),
            settings.model_alias.lower(),
            str(settings.model_dir).lower(),
        ]
    )
    if "2bit" in marker or "2-bit" in marker:
        return 2
    if "4bit" in marker or "4-bit" in marker:
        return 4
    return None


def repair_model_config(
    model_dir: Path,
    *,
    quant_bits: int | None,
    backup: bool = True,
) -> RepairResult:
    if quant_bits is None:
        return RepairResult(False, "no expected quantization bit-width detected")

    config_path = model_dir / "config.json"
    if not config_path.exists():
        return RepairResult(False, f"config not found: {config_path}")

    tokenizer_changed = repair_tokenizer_chat_template(model_dir, backup=backup)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    quantization = config.get("quantization")
    if not isinstance(quantization, dict):
        return RepairResult(False, "config has no quantization block")

    current_bits = quantization.get("bits")
    override_changes = normalize_quantization_overrides(quantization, quant_bits)
    override_change_count = len(override_changes)
    if current_bits == quant_bits and override_change_count == 0 and not tokenizer_changed:
        return RepairResult(False, f"quantization metadata already matches {quant_bits}-bit")

    if backup:
        backup_path = config_path.with_suffix(".json.bak")
        if not backup_path.exists():
            shutil.copy2(config_path, backup_path)

    quantization["bits"] = quant_bits
    config_path.write_text(json.dumps(config, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return RepairResult(
        True,
        (
            f"set quantization.bits from {current_bits} to {quant_bits}; "
            f"updated {override_change_count} per-layer override fields; "
            f"tokenizer chat_template {'updated' if tokenizer_changed else 'unchanged'}"
        ),
    )


def normalize_quantization_overrides(quantization: dict[str, object], quant_bits: int) -> list[str]:
    if quant_bits != 2:
        return []

    changes: list[str] = []
    for key, value in quantization.items():
        if not isinstance(value, dict):
            continue
        if value.get("bits") == 8:
            value["bits"] = 4
            changes.append(f"{key}.bits")
        if value.get("bits") == 4 and value.get("group_size") == 64:
            value["group_size"] = 32
            changes.append(f"{key}.group_size")
    return changes


def repair_tokenizer_chat_template(model_dir: Path, *, backup: bool = True) -> bool:
    tokenizer_config_path = model_dir / "tokenizer_config.json"
    chat_template_path = model_dir / "chat_template.jinja"
    if not tokenizer_config_path.exists() or not chat_template_path.exists():
        return False

    tokenizer_config = json.loads(tokenizer_config_path.read_text(encoding="utf-8"))
    chat_template = chat_template_path.read_text(encoding="utf-8")
    if tokenizer_config.get("chat_template") == chat_template:
        return False

    if backup:
        backup_path = tokenizer_config_path.with_suffix(".json.bak")
        if not backup_path.exists():
            shutil.copy2(tokenizer_config_path, backup_path)

    tokenizer_config["chat_template"] = chat_template
    tokenizer_config_path.write_text(
        json.dumps(tokenizer_config, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return True


def repair_from_settings(settings: Settings) -> RepairResult:
    return repair_model_config(settings.model_dir, quant_bits=expected_bits(settings))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair local MLX model config metadata.")
    parser.add_argument("--env-file", default=".env", help="Path to env file.")
    parser.add_argument(
        "--bits",
        type=int,
        default=None,
        help="Expected default quantization bits.",
    )
    parser.add_argument("--no-backup", action="store_true", help="Do not create config.json.bak.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from_env(args.env_file)
    bits = args.bits if args.bits is not None else expected_bits(settings)
    result = repair_model_config(settings.model_dir, quant_bits=bits, backup=not args.no_backup)
    print(result.message)
    return 0
