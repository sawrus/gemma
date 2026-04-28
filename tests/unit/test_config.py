from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from gemma_local_agent.config import parse_env_file, redact_mapping, settings_from_env


class ConfigTests(unittest.TestCase):
    def test_parse_env_file_handles_quotes_and_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "HF_TOKEN='secret-token'\n# comment\nGEMMA_PORT=9090\nEMPTY=\n",
                encoding="utf-8",
            )
            self.assertEqual(
                parse_env_file(env_path),
                {"HF_TOKEN": "secret-token", "GEMMA_PORT": "9090", "EMPTY": ""},
            )

    def test_settings_from_env_loads_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("HF_TOKEN=abc12345xyz\nGEMMA_PORT=9091\n", encoding="utf-8")
            old_token = os.environ.pop("HF_TOKEN", None)
            old_port = os.environ.pop("GEMMA_PORT", None)
            try:
                settings = settings_from_env(env_path)
                self.assertEqual(settings.hf_token, "abc12345xyz")
                self.assertEqual(settings.port, 9091)
            finally:
                if old_token is not None:
                    os.environ["HF_TOKEN"] = old_token
                if old_port is not None:
                    os.environ["GEMMA_PORT"] = old_port

    def test_redact_mapping_hides_hf_token(self) -> None:
        values = redact_mapping({"HF_TOKEN": "hf_abcdefghijklmnopqrstuvwxyz", "GEMMA_PORT": "8080"})
        self.assertEqual(values["GEMMA_PORT"], "8080")
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", values["HF_TOKEN"])


if __name__ == "__main__":
    unittest.main()

