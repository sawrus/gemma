#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gemma_local_agent.benchmark import chat_completion  # noqa: E402
from gemma_local_agent.config import settings_from_env  # noqa: E402
from gemma_local_agent.server import ServerOptions, build_command, wait_for_server  # noqa: E402


def main() -> int:
    if os.environ.get("RUN_REAL_MODEL_TESTS") != "1":
        print("RUN_REAL_MODEL_TESTS=1 is required for real smoke tests")
        return 2
    settings = settings_from_env()
    command = build_command(ServerOptions(settings=settings))
    process = subprocess.Popen(command)
    try:
        wait_for_server(settings.base_url, timeout_seconds=180)
        response = chat_completion(
            base_url=settings.base_url,
            model=settings.model_id,
            prompt="Reply with exactly: ok",
            max_tokens=8,
        )
        if "choices" not in response:
            raise RuntimeError("chat completion response did not include choices")
        print("real smoke test passed")
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
