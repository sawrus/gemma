from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gemma_local_agent.config import Settings
from gemma_local_agent.model_repair import (
    expected_bits,
    repair_model_config,
    repair_tokenizer_chat_template,
)


class ModelRepairTests(unittest.TestCase):
    def test_expected_bits_detects_2bit_profile(self) -> None:
        settings = Settings(
            hf_token="",
            hf_home=".cache/huggingface",
            model_id="vendor/model-2bit",
            model_alias="model-local",
            model_dir=Path(".models/model-2bit"),
            host="127.0.0.1",
            port=8080,
            backend_port=18080,
            backend_module="mlx_lm.server",
            kv_bits="3.5",
            kv_quant_scheme="turboquant",
        )
        self.assertEqual(expected_bits(settings), 2)

    def test_repair_model_config_updates_default_bits_and_preserves_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_dir = Path(tmp)
            config_path = model_dir / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "quantization": {
                            "bits": 4,
                            "group_size": 64,
                            "language_model.model.layers.0.mlp.gate_proj": {
                                "bits": 8,
                                "group_size": 64,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = repair_model_config(model_dir, quant_bits=2)
            repaired = json.loads(config_path.read_text(encoding="utf-8"))

            self.assertTrue(result.changed)
            self.assertEqual(repaired["quantization"]["bits"], 2)
            self.assertEqual(
                repaired["quantization"]["language_model.model.layers.0.mlp.gate_proj"][
                    "bits"
                ],
                4,
            )
            self.assertEqual(
                repaired["quantization"]["language_model.model.layers.0.mlp.gate_proj"][
                    "group_size"
                ],
                32,
            )
            self.assertTrue((model_dir / "config.json.bak").exists())

    def test_repair_model_config_is_idempotent_for_2bit_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_dir = Path(tmp)
            config_path = model_dir / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "quantization": {
                            "bits": 2,
                            "language_model.model.layers.0.mlp.gate_proj": {
                                "bits": 4,
                                "group_size": 32,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = repair_model_config(model_dir, quant_bits=2)
            self.assertFalse(result.changed)

    def test_repair_tokenizer_chat_template_copies_sidecar_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_dir = Path(tmp)
            (model_dir / "tokenizer_config.json").write_text("{}", encoding="utf-8")
            (model_dir / "chat_template.jinja").write_text("{{ bos_token }}", encoding="utf-8")
            changed = repair_tokenizer_chat_template(model_dir)
            tokenizer_config = json.loads(
                (model_dir / "tokenizer_config.json").read_text(encoding="utf-8")
            )

            self.assertTrue(changed)
            self.assertEqual(tokenizer_config["chat_template"], "{{ bos_token }}")
            self.assertTrue((model_dir / "tokenizer_config.json.bak").exists())


if __name__ == "__main__":
    unittest.main()
