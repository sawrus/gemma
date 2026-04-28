from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from gemma_local_agent.config import settings_from_env

PROMPTS: dict[str, str] = {
    "short_chat": "Explain in two sentences what makes a local LLM useful for coding agents.",
    "coding_edit": (
        "Refactor this Python function for clarity and explain the changes:\n"
        "def f(xs):\n"
        "    r=[]\n"
        "    for x in xs:\n"
        "        if x and x%2==0:r.append(x*x)\n"
        "    return r"
    ),
    "json_tool": (
        "Return JSON with keys action, risk, and commands for checking whether a local "
        "OpenAI-compatible server is healthy."
    ),
    "long_context": (
        "Summarize this operational constraint for an engineering handoff: "
        + "local model must fit into 16 GB unified memory with enough spare RAM for Codex. " * 80
    ),
    "agent_planning": (
        "Create a concise implementation plan for adding retry handling to a CLI that calls "
        "an OpenAI-compatible local model server."
    ),
}


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    prompt: str


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def chat_completion(
    *,
    base_url: str,
    model: str,
    prompt: str,
    api_key: str = "local",
    max_tokens: int = 256,
) -> dict[str, Any]:
    try:
        return openai_sdk_chat_completion(
            base_url=base_url,
            model=model,
            prompt=prompt,
            api_key=api_key,
            max_tokens=max_tokens,
        )
    except ImportError:
        return http_chat_completion(
            base_url=base_url,
            model=model,
            prompt=prompt,
            api_key=api_key,
            max_tokens=max_tokens,
        )


def openai_sdk_chat_completion(
    *,
    base_url: str,
    model: str,
    prompt: str,
    api_key: str,
    max_tokens: int,
) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    if hasattr(completion, "model_dump"):
        return completion.model_dump()
    return json.loads(completion.model_dump_json())


def http_chat_completion(
    *,
    base_url: str,
    model: str,
    prompt: str,
    api_key: str,
    max_tokens: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "")


def usage_tokens(response: dict[str, Any], prompt: str, content: str) -> tuple[int, int]:
    usage = response.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or estimate_tokens(prompt))
    completion_tokens = int(usage.get("completion_tokens") or estimate_tokens(content))
    return prompt_tokens, completion_tokens


def run_benchmark_case(
    case: BenchmarkCase,
    *,
    base_url: str,
    model: str,
    api_key: str = "local",
    max_tokens: int = 256,
) -> dict[str, Any]:
    started = time.perf_counter()
    response = chat_completion(
        base_url=base_url,
        model=model,
        prompt=case.prompt,
        api_key=api_key,
        max_tokens=max_tokens,
    )
    elapsed = time.perf_counter() - started
    content = extract_text(response)
    prompt_tokens, completion_tokens = usage_tokens(response, case.prompt, content)
    total_tokens = prompt_tokens + completion_tokens
    return {
        "name": case.name,
        "latency_seconds": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "completion_tokens_per_second": completion_tokens / elapsed if elapsed else 0.0,
        "total_tokens_per_second": total_tokens / elapsed if elapsed else 0.0,
        "response_preview": content[:240],
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(item["latency_seconds"]) for item in results]
    completion_rates = [float(item["completion_tokens_per_second"]) for item in results]
    return {
        "case_count": len(results),
        "latency_p50_seconds": statistics.median(latencies) if latencies else 0.0,
        "latency_max_seconds": max(latencies) if latencies else 0.0,
        "completion_tokens_per_second_avg": (
            statistics.fmean(completion_rates) if completion_rates else 0.0
        ),
    }


def write_reports(
    *,
    output_dir: Path,
    label: str,
    model: str,
    base_url: str,
    kv_bits: str,
    kv_quant_scheme: str,
    results: list[dict[str, Any]],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "created_at": timestamp,
        "label": label,
        "model": model,
        "base_url": base_url,
        "kv_bits": kv_bits,
        "kv_quant_scheme": kv_quant_scheme,
        "summary": summarize_results(results),
        "results": results,
    }
    json_path = output_dir / f"{timestamp}-{label}.json"
    md_path = output_dir / f"{timestamp}-{label}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Gemma Local Benchmark: {report['label']}",
        "",
        f"- Model: `{report['model']}`",
        f"- Base URL: `{report['base_url']}`",
        f"- KV cache: `{report['kv_quant_scheme']}` / `{report['kv_bits']}` bits",
        "",
        "| Case | Latency s | Completion tok/s | Total tokens |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item in report["results"]:
        lines.append(
            f"| {item['name']} | {item['latency_seconds']:.3f} | "
            f"{item['completion_tokens_per_second']:.2f} | {item['total_tokens']} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark a local OpenAI-compatible model server."
    )
    parser.add_argument("--env-file", default=".env", help="Path to env file.")
    parser.add_argument("--base-url", default=None, help="OpenAI-compatible base URL.")
    parser.add_argument("--model", default=None, help="Model name to send in requests.")
    parser.add_argument("--api-key", default="local", help="API key placeholder.")
    parser.add_argument(
        "--output-dir",
        default="reports/benchmarks",
        help="Report output directory.",
    )
    parser.add_argument("--label", default="local", help="Report label.")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256,
        help="Max completion tokens per case.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from_env(args.env_file)
    base_url = args.base_url or settings.base_url
    model = args.model or settings.model_id
    cases = [BenchmarkCase(name=name, prompt=prompt) for name, prompt in PROMPTS.items()]
    results = [
        run_benchmark_case(
            case,
            base_url=base_url,
            model=model,
            api_key=args.api_key,
            max_tokens=args.max_tokens,
        )
        for case in cases
    ]
    json_path, md_path = write_reports(
        output_dir=Path(args.output_dir),
        label=args.label,
        model=model,
        base_url=base_url,
        kv_bits=settings.kv_bits,
        kv_quant_scheme=settings.kv_quant_scheme,
        results=results,
    )
    print(f"benchmark reports written: {json_path}, {md_path}")
    return 0
