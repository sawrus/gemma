from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class BenchmarkE2ETests(unittest.TestCase):
    def test_benchmark_script_writes_reports_against_fake_server(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            port = free_port()
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{repo_root / 'src'}:{repo_root}"
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "tests.e2e.fake_openai_server",
                    "--model",
                    "fake/model",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--kv-bits",
                    "3.5",
                    "--kv-quant-scheme",
                    "turboquant",
                ],
                cwd=repo_root,
                env=env,
            )
            try:
                time.sleep(0.5)
                result = subprocess.run(
                    [
                        sys.executable,
                        str(repo_root / "scripts/benchmark_model.py"),
                        "--base-url",
                        f"http://127.0.0.1:{port}/v1",
                        "--model",
                        "fake/model",
                        "--output-dir",
                        str(tmp_path / "reports"),
                        "--label",
                        "e2e",
                    ],
                    cwd=repo_root,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=True,
                )
                self.assertIn("benchmark reports written", result.stdout)
                self.assertEqual(len(list((tmp_path / "reports").glob("*-e2e.json"))), 1)
                self.assertEqual(len(list((tmp_path / "reports").glob("*-e2e.md"))), 1)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()


if __name__ == "__main__":
    unittest.main()

