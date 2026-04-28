from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    server_version = "FakeOpenAI/1.0"

    def _send(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send({"ok": True, "kv_quant_scheme": self.server.kv_quant_scheme})
            return
        if self.path in {"/models", "/v1/models"}:
            self._send({"object": "list", "data": [{"id": self.server.model}]})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length).decode("utf-8"))
        prompt = request["messages"][0]["content"]
        content = f"fake response for {request['model']}"
        self._send(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
                "usage": {
                    "prompt_tokens": len(str(prompt).split()),
                    "completion_tokens": len(content.split()),
                    "total_tokens": len(str(prompt).split()) + len(content.split()),
                },
            }
        )

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--kv-bits", default="3.5")
    parser.add_argument("--kv-quant-scheme", default="turboquant")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.model = args.model
    server.kv_bits = args.kv_bits
    server.kv_quant_scheme = args.kv_quant_scheme
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
