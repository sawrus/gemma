from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gemma_local_agent.config import Settings
from gemma_local_agent.download import DownloadOptions, download_model, manifest_payload


class DownloadTests(unittest.TestCase):
    def test_download_passes_token_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            captured: dict[str, object] = {}
            model_dir = Path(tmp) / "model"
            settings = Settings(
                hf_token="hf_secret_token",
                hf_home=str(Path(tmp) / "hf"),
                model_id="fake/model",
                model_alias="fake-local",
                model_dir=model_dir,
                host="127.0.0.1",
                port=18080,
                backend_port=18081,
                backend_module="mlx_lm.server",
                kv_bits="3.5",
                kv_quant_scheme="turboquant",
            )

            def fake_snapshot(**kwargs: object) -> str:
                captured.update(kwargs)
                model_dir.mkdir(parents=True, exist_ok=True)
                (model_dir / "config.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
                return str(model_dir)

            with (
                patch("gemma_local_agent.download.platform_guard") as platform_guard,
                patch("gemma_local_agent.download.memory_guard") as mem_guard,
            ):
                platform_guard.return_value.allowed = True
                platform_guard.return_value.messages = ("platform ok",)
                mem_guard.return_value.allowed = True
                mem_guard.return_value.messages = ("memory ok",)
                manifest = download_model(
                    DownloadOptions(settings=settings),
                    snapshot_download_func=fake_snapshot,
                )

            self.assertEqual(captured["token"], "hf_secret_token")
            payload = manifest_payload(manifest)
            self.assertEqual(payload["model_id"], "fake/model")
            self.assertEqual(payload["file_count"], 1)


if __name__ == "__main__":
    unittest.main()
