from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma_local_agent.config import Settings
from gemma_local_agent.server import ServerOptions, build_command, model_source


def make_settings(model_dir: Path) -> Settings:
    return Settings(
        hf_token="",
        hf_home=".cache/huggingface",
        model_id="fake/model",
        model_alias="fake-local",
        model_dir=model_dir,
        host="127.0.0.1",
        port=18080,
        backend_port=18081,
        kv_bits="3.5",
        kv_quant_scheme="turboquant",
    )


class ServerTests(unittest.TestCase):
    def test_model_source_requires_local_manifest_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp) / "model")
            with self.assertRaisesRegex(RuntimeError, "Run `make model-download` first"):
                model_source(settings)

    def test_model_source_allows_explicit_remote_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp) / "model")
            self.assertEqual(model_source(settings, allow_remote_model=True), "fake/model")

    def test_build_command_uses_local_manifest_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_dir = Path(tmp) / "model"
            model_dir.mkdir()
            (model_dir / "manifest.json").write_text("{}", encoding="utf-8")
            settings = make_settings(model_dir)
            command = build_command(ServerOptions(settings=settings))
            self.assertIn(str(model_dir.resolve()), command)
            self.assertNotIn("fake/model", command)


if __name__ == "__main__":
    unittest.main()
