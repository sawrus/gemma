from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from gemma_local_agent.config import Settings, settings_from_env


@dataclass(frozen=True)
class ServerOptions:
    settings: Settings
    backend_module: str = "mlx_vlm.server"
    timeout_seconds: float = 120.0
    smoke_only: bool = False


def model_source(settings: Settings) -> str:
    return str(settings.model_dir) if settings.model_dir.exists() else settings.model_id


def build_command(options: ServerOptions) -> list[str]:
    settings = options.settings
    return [
        sys.executable,
        "-m",
        options.backend_module,
        "--model",
        model_source(settings),
        "--host",
        settings.host,
        "--port",
        str(settings.port),
        "--kv-bits",
        settings.kv_bits,
        "--kv-quant-scheme",
        settings.kv_quant_scheme,
    ]


def ensure_port_available(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        if sock.connect_ex((host, port)) == 0:
            raise RuntimeError(f"port already in use: {host}:{port}")


def wait_for_server(base_url: str, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    urls = [base_url.replace("/v1", "/health"), f"{base_url}/models"]
    last_error = "server did not respond"
    while time.monotonic() < deadline:
        for url in urls:
            try:
                request = Request(url, headers={"Accept": "application/json"})
                with urlopen(request, timeout=1.0) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body) if body else {"ok": True}
            except (OSError, URLError, json.JSONDecodeError) as exc:
                last_error = str(exc)
        time.sleep(0.25)
    raise TimeoutError(f"server health check failed after {timeout_seconds:.1f}s: {last_error}")


def start_server(options: ServerOptions) -> int:
    ensure_port_available(options.settings.host, options.settings.port)
    command = build_command(options)
    process = subprocess.Popen(command)
    try:
        wait_for_server(options.settings.base_url, options.timeout_seconds)
        print(f"server is healthy at {options.settings.base_url}")
        if options.smoke_only:
            return 0
        return process.wait()
    finally:
        if options.smoke_only and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start OpenAI-compatible mlx-vlm server.")
    parser.add_argument("--env-file", default=".env", help="Path to env file.")
    parser.add_argument("--backend-module", default="mlx_vlm.server", help="Python module to run.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Health-check timeout in seconds.",
    )
    parser.add_argument("--smoke-only", action="store_true", help="Start, health-check, then stop.")
    parser.add_argument("--print-command", action="store_true", help="Print command JSON and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    options = ServerOptions(
        settings=settings_from_env(args.env_file),
        backend_module=args.backend_module,
        timeout_seconds=args.timeout,
        smoke_only=args.smoke_only,
    )
    command = build_command(options)
    if args.print_command:
        print(json.dumps(command, indent=2))
        return 0
    return start_server(options)
