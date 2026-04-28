from __future__ import annotations

import json
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass(frozen=True)
class ProxyConfig:
    listen_host: str
    listen_port: int
    backend_host: str
    backend_port: int
    model_alias: str
    local_model: str
    upstream_model_id: str

    @property
    def listen_base_url(self) -> str:
        return f"http://{self.listen_host}:{self.listen_port}/v1"


def rewrite_model_payload(
    payload: dict[str, Any],
    *,
    model_alias: str,
    local_model: str,
    upstream_model_id: str,
) -> dict[str, Any]:
    rewritten = dict(payload)
    requested_model = rewritten.get("model")
    if requested_model in {model_alias, upstream_model_id, local_model}:
        rewritten["model"] = local_model
    return rewritten


def model_list_payload(config: ProxyConfig) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": config.model_alias,
                "object": "model",
                "owned_by": "local",
            }
        ],
    }


class AliasProxyHandler(BaseHTTPRequestHandler):
    server: AliasProxyServer

    def do_GET(self) -> None:
        if self.path in {"/models", "/v1/models"}:
            self.send_json(model_list_payload(self.server.config))
            return
        self.forward()

    def do_POST(self) -> None:
        self.forward()

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def forward(self) -> None:
        body = self.read_request_body()
        headers = self.forward_headers()
        if body and self.headers.get("Content-Type", "").startswith("application/json"):
            body = self.rewrite_json_body(body)
            headers["Content-Length"] = str(len(body))

        connection = HTTPConnection(
            self.server.config.backend_host,
            self.server.config.backend_port,
            timeout=300,
        )
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            self.copy_response(response)
        finally:
            connection.close()

    def read_request_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return None
        return self.rfile.read(length)

    def rewrite_json_body(self, body: bytes) -> bytes:
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return body
        if not isinstance(payload, dict):
            return body
        rewritten = rewrite_model_payload(
            payload,
            model_alias=self.server.config.model_alias,
            local_model=self.server.config.local_model,
            upstream_model_id=self.server.config.upstream_model_id,
        )
        return json.dumps(rewritten).encode("utf-8")

    def forward_headers(self) -> dict[str, str]:
        return {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS
        }

    def copy_response(self, response: HTTPResponse) -> None:
        self.send_response(response.status, response.reason)
        for key, value in response.getheaders():
            if key.lower() not in HOP_BY_HOP_HEADERS:
                self.send_header(key, value)
        self.end_headers()
        while chunk := response.read(65536):
            self.wfile.write(chunk)
            self.wfile.flush()

    def log_message(self, format: str, *args: object) -> None:
        return


class AliasProxyServer(ThreadingHTTPServer):
    def __init__(self, config: ProxyConfig):
        super().__init__((config.listen_host, config.listen_port), AliasProxyHandler)
        self.config = config

