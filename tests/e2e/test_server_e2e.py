from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ServerE2ETests(unittest.TestCase):
    def test_serve_script_starts_fake_backend_with_env_config(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            model_dir = tmp_path / "model"
            model_dir.mkdir()
            port = free_port()
            env_path = tmp_path / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "HF_TOKEN=hf_should_not_leak",
                        "GEMMA_MODEL_ID=fake/model",
                        f"GEMMA_MODEL_DIR={model_dir}",
                        "GEMMA_HOST=127.0.0.1",
                        f"GEMMA_PORT={port}",
                        "GEMMA_KV_BITS=3.5",
                        "GEMMA_KV_QUANT_SCHEME=turboquant",
                    ]
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{repo_root / 'src'}:{repo_root}"
            result = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts/serve_openai.py"),
                    "--env-file",
                    str(env_path),
                    "--backend-module",
                    "tests.e2e.fake_openai_server",
                    "--smoke-only",
                    "--timeout",
                    "5",
                ],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            output = result.stdout + result.stderr
            self.assertIn("server is healthy", output)
            self.assertNotIn("hf_should_not_leak", output)


if __name__ == "__main__":
    unittest.main()

