from __future__ import annotations

import unittest

from gemma_local_agent.proxy import ProxyConfig, model_list_payload, rewrite_model_payload


class ProxyTests(unittest.TestCase):
    def test_rewrite_model_payload_maps_alias_to_local_path(self) -> None:
        payload = {"model": "gemma4-local", "messages": []}
        rewritten = rewrite_model_payload(
            payload,
            model_alias="gemma4-local",
            local_model="/models/gemma4",
            upstream_model_id="hf/gemma4",
        )
        self.assertEqual(rewritten["model"], "/models/gemma4")

    def test_rewrite_model_payload_maps_hf_id_to_local_path(self) -> None:
        payload = {"model": "hf/gemma4", "messages": []}
        rewritten = rewrite_model_payload(
            payload,
            model_alias="gemma4-local",
            local_model="/models/gemma4",
            upstream_model_id="hf/gemma4",
        )
        self.assertEqual(rewritten["model"], "/models/gemma4")

    def test_model_list_exposes_alias_only(self) -> None:
        payload = model_list_payload(
            ProxyConfig(
                listen_host="127.0.0.1",
                listen_port=8080,
                backend_host="127.0.0.1",
                backend_port=18080,
                model_alias="gemma4-local",
                local_model="/models/gemma4",
                upstream_model_id="hf/gemma4",
            )
        )
        self.assertEqual(payload["data"][0]["id"], "gemma4-local")


if __name__ == "__main__":
    unittest.main()

