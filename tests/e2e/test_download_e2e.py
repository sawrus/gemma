from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class DownloadE2ETests(unittest.TestCase):
    def test_script_downloads_with_fake_hf_backend_and_redacts_output(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_module = tmp_path / "huggingface_hub.py"
            model_dir = tmp_path / "model"
            fake_module.write_text(
                textwrap.dedent(
                    f"""
                    from pathlib import Path

                    def snapshot_download(**kwargs):
                        assert kwargs["token"] == "hf_super_secret"
                        path = Path({str(model_dir)!r})
                        path.mkdir(parents=True, exist_ok=True)
                        (path / "config.json").write_text("{{}}", encoding="utf-8")
                        return str(path)
                    """
                ),
                encoding="utf-8",
            )
            env_path = tmp_path / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "HF_TOKEN=hf_super_secret",
                        "GEMMA_MODEL_ID=fake/model",
                        f"GEMMA_MODEL_DIR={model_dir}",
                        "GEMMA_PORT=18181",
                    ]
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{tmp_path}:{repo_root / 'src'}"
            result = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts/download_model.py"),
                    "--env-file",
                    str(env_path),
                    "--force",
                ],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertTrue((model_dir / "manifest.json").exists())
            self.assertNotIn("hf_super_secret", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

