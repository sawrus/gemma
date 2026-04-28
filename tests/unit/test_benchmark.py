from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma_local_agent.benchmark import (
    BenchmarkCase,
    extract_text,
    render_markdown,
    summarize_results,
    usage_tokens,
    write_reports,
)


class BenchmarkTests(unittest.TestCase):
    def test_extract_text_and_usage_fallback(self) -> None:
        response = {"choices": [{"message": {"content": "hello local model"}}]}
        content = extract_text(response)
        prompt_tokens, completion_tokens = usage_tokens(response, "say hello", content)
        self.assertEqual(content, "hello local model")
        self.assertEqual(prompt_tokens, 2)
        self.assertEqual(completion_tokens, 3)

    def test_summary_and_reports(self) -> None:
        results = [
            {
                "name": "case",
                "latency_seconds": 2.0,
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
                "completion_tokens_per_second": 10.0,
                "total_tokens_per_second": 15.0,
                "response_preview": "ok",
            }
        ]
        summary = summarize_results(results)
        self.assertEqual(summary["case_count"], 1)
        with tempfile.TemporaryDirectory() as tmp:
            json_path, md_path = write_reports(
                output_dir=Path(tmp),
                label="unit",
                model="fake",
                base_url="http://127.0.0.1:1/v1",
                kv_bits="3.5",
                kv_quant_scheme="turboquant",
                results=results,
            )
            self.assertTrue(json_path.exists())
            self.assertIn("turboquant", md_path.read_text(encoding="utf-8"))

    def test_benchmark_case_dataclass(self) -> None:
        case = BenchmarkCase(name="x", prompt="y")
        self.assertEqual(case.name, "x")
        self.assertEqual(case.prompt, "y")

    def test_render_markdown_contains_table(self) -> None:
        markdown = render_markdown(
            {
                "label": "unit",
                "model": "fake",
                "base_url": "http://local/v1",
                "kv_quant_scheme": "turboquant",
                "kv_bits": "3.5",
                "results": [
                    {
                        "name": "case",
                        "latency_seconds": 1.0,
                        "completion_tokens_per_second": 2.0,
                        "total_tokens": 3,
                    }
                ],
            }
        )
        self.assertIn("| Case |", markdown)


if __name__ == "__main__":
    unittest.main()

