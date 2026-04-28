from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass

from gemma_local_agent.config import DEFAULT_MODEL_DIR, DEFAULT_MODEL_ID


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model_id: str
    model_dir: str
    expected_size_gb: float
    minimum_memory_gb: float
    description: str


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    messages: tuple[str, ...]


DEFAULT_PROFILE = "26b-a4b-tq-2bit"

PROFILES: dict[str, ModelProfile] = {
    DEFAULT_PROFILE: ModelProfile(
        name=DEFAULT_PROFILE,
        model_id=DEFAULT_MODEL_ID,
        model_dir=DEFAULT_MODEL_DIR,
        expected_size_gb=7.0,
        minimum_memory_gb=12.0,
        description="Gemma 4 26B A4B instruction model, MLX TurboQuant 2-bit.",
    ),
    "26b-a4b-tq-4bit": ModelProfile(
        name="26b-a4b-tq-4bit",
        model_id="majentik/gemma-4-26B-A4B-it-TurboQuant-MLX-4bit",
        model_dir=".models/gemma4-26b-a4b-it-tq-4bit",
        expected_size_gb=15.6,
        minimum_memory_gb=24.0,
        description="Gemma 4 26B A4B instruction model, MLX TurboQuant 4-bit quality profile.",
    ),
}


def select_profile(name: str | None = None) -> ModelProfile:
    profile_name = name or DEFAULT_PROFILE
    try:
        return PROFILES[profile_name]
    except KeyError as exc:
        names = ", ".join(sorted(PROFILES))
        raise ValueError(
            f"unknown model profile '{profile_name}'. Available profiles: {names}"
        ) from exc


def total_memory_gb() -> float | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None
    return pages * page_size / (1024**3)


def platform_guard(force: bool = False) -> GuardResult:
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return GuardResult(True, ("platform ok: macOS arm64",))
    message = "expected macOS arm64 Apple Silicon for MLX runtime"
    if force:
        return GuardResult(True, (f"warning: {message}",))
    return GuardResult(False, (message,))


def memory_guard(
    profile: ModelProfile,
    memory_gb: float | None = None,
    force: bool = False,
) -> GuardResult:
    total_gb = total_memory_gb() if memory_gb is None else memory_gb
    if total_gb is None:
        message = "could not detect total system memory"
        if force:
            return GuardResult(True, (f"warning: {message}",))
        return GuardResult(False, (message,))
    if total_gb < profile.minimum_memory_gb:
        message = (
            f"profile {profile.name} expects at least {profile.minimum_memory_gb:.1f} GB RAM; "
            f"detected {total_gb:.1f} GB"
        )
        if force:
            return GuardResult(True, (f"warning: {message}",))
        return GuardResult(False, (message,))
    spare_gb = total_gb - profile.expected_size_gb
    return GuardResult(
        True,
        (
            f"memory ok: detected {total_gb:.1f} GB, model footprint about "
            f"{profile.expected_size_gb:.1f} GB, spare about {spare_gb:.1f} GB",
        ),
    )
