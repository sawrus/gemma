from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from gemma_local_agent.config import Settings, settings_from_env
from gemma_local_agent.model_repair import repair_from_settings
from gemma_local_agent.proxy import AliasProxyServer, ProxyConfig


@dataclass(frozen=True)
class ServerOptions:
    settings: Settings
    backend_module: str = "mlx_lm.server"
    timeout_seconds: float = 120.0
    smoke_only: bool = False
    allow_remote_model: bool = False
    alias_proxy: bool = True
    startup_preflight: bool = True


def model_manifest_path(settings: Settings) -> str:
    return str(settings.model_dir / "manifest.json")


def model_source(settings: Settings, *, allow_remote_model: bool = False) -> str:
    manifest_path = settings.model_dir / "manifest.json"
    if manifest_path.exists():
        return str(settings.model_dir.resolve())
    if allow_remote_model:
        return settings.model_id
    raise RuntimeError(
        "local model is not downloaded or manifest is missing. "
        f"Expected manifest: {manifest_path.resolve()}. "
        "Run `make model-download` first, or pass `--allow-remote-model` "
        "to let the backend download lazily from Hugging Face."
    )


def build_command(options: ServerOptions) -> list[str]:
    settings = options.settings
    port = settings.backend_port if options.alias_proxy else settings.port
    command = [
        sys.executable,
        "-m",
        options.backend_module,
        "--model",
        model_source(settings, allow_remote_model=options.allow_remote_model),
        "--host",
        settings.host,
        "--port",
        str(port),
    ]
    if options.backend_module == "mlx_vlm.server":
        command.extend(
            [
                "--kv-bits",
                settings.kv_bits,
                "--kv-quant-scheme",
                settings.kv_quant_scheme,
            ]
        )
    return command


def backend_base_url(options: ServerOptions) -> str:
    port = options.settings.backend_port if options.alias_proxy else options.settings.port
    return f"http://{options.settings.host}:{port}/v1"


def build_proxy_config(options: ServerOptions) -> ProxyConfig:
    return ProxyConfig(
        listen_host=options.settings.host,
        listen_port=options.settings.port,
        backend_host=options.settings.host,
        backend_port=options.settings.backend_port,
        model_alias=options.settings.model_alias,
        local_model=model_source(
            options.settings,
            allow_remote_model=options.allow_remote_model,
        ),
        upstream_model_id=options.settings.model_id,
    )


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


def wait_for_model_ready(
    *,
    base_url: str,
    model: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with ok."}],
        "max_tokens": 1,
        "temperature": 0,
    }
    body = json.dumps(payload).encode("utf-8")
    last_error = "model preflight did not run"
    while time.monotonic() < deadline:
        try:
            request = Request(
                f"{base_url.rstrip('/')}/chat/completions",
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": "Bearer local",
                },
            )
            with urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
                return json.loads(response_body) if response_body else {"ok": True}
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(1.0)
    raise TimeoutError(
        f"model preflight failed after {timeout_seconds:.1f}s: {last_error}"
    )


def start_server(options: ServerOptions) -> int:
    ensure_port_available(options.settings.host, options.settings.port)
    if options.alias_proxy:
        if options.settings.port == options.settings.backend_port:
            raise RuntimeError(
                "GEMMA_PORT and GEMMA_BACKEND_PORT must differ "
                "when alias proxy is enabled"
            )
        ensure_port_available(options.settings.host, options.settings.backend_port)
    repair_result = repair_from_settings(options.settings)
    if repair_result.changed:
        print(f"model config repaired: {repair_result.message}")
    command = build_command(options)
    model_arg = command[command.index("--model") + 1]
    print(
        f"starting {options.backend_module} backend "
        f"with local model source: {model_arg}"
    )
    process = subprocess.Popen(command)
    proxy_server: AliasProxyServer | None = None
    try:
        wait_for_server(backend_base_url(options), options.timeout_seconds)
        if options.startup_preflight:
            wait_for_model_ready(
                base_url=backend_base_url(options),
                model=model_arg,
                timeout_seconds=options.timeout_seconds,
            )
            print("backend model preflight passed")
        if options.alias_proxy:
            proxy_config = build_proxy_config(options)
            proxy_server = AliasProxyServer(proxy_config)
            proxy_thread = threading.Thread(target=proxy_server.serve_forever, daemon=True)
            proxy_thread.start()
            wait_for_server(proxy_config.listen_base_url, 5)
            print(
                "alias proxy is healthy at "
                f"{proxy_config.listen_base_url}; model alias: {proxy_config.model_alias}"
            )
        else:
            print(f"server is healthy at {options.settings.base_url}")
        if options.smoke_only:
            return 0
        return process.wait()
    finally:
        if proxy_server is not None:
            proxy_server.shutdown()
            proxy_server.server_close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start OpenAI-compatible MLX server.")
    parser.add_argument("--env-file", default=".env", help="Path to env file.")
    parser.add_argument(
        "--backend-module",
        default=None,
        help="Python module to run. Defaults to GEMMA_BACKEND_MODULE.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Health-check timeout in seconds.",
    )
    parser.add_argument("--smoke-only", action="store_true", help="Start, health-check, then stop.")
    parser.add_argument("--print-command", action="store_true", help="Print command JSON and exit.")
    parser.add_argument(
        "--no-startup-preflight",
        action="store_true",
        help="Skip the one-token startup request that verifies model loading.",
    )
    parser.add_argument(
        "--allow-remote-model",
        action="store_true",
        help="Allow backend to use HF model id and download lazily if local manifest is missing.",
    )
    parser.add_argument(
        "--no-alias-proxy",
        action="store_true",
        help="Expose the MLX backend directly instead of mapping a short model alias.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from_env(args.env_file)
    options = ServerOptions(
        settings=settings,
        backend_module=args.backend_module or settings.backend_module,
        timeout_seconds=args.timeout,
        smoke_only=args.smoke_only,
        allow_remote_model=args.allow_remote_model,
        alias_proxy=not args.no_alias_proxy,
        startup_preflight=not args.no_startup_preflight,
    )
    command = build_command(options)
    if args.print_command:
        payload: dict[str, Any] = {
            "backend_command": command,
            "backend_base_url": backend_base_url(options),
        }
        if options.alias_proxy:
            proxy_config = build_proxy_config(options)
            payload["public_base_url"] = proxy_config.listen_base_url
            payload["model_alias"] = proxy_config.model_alias
        print(json.dumps(payload, indent=2))
        return 0
    return start_server(options)
