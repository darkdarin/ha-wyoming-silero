"""Home Assistant app glue: options and Wyoming discovery against a fake Supervisor."""

import asyncio
import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from wyoming_silero import supervisor
from wyoming_silero.__main__ import parse_args


def test_options_become_arguments(tmp_path: Path) -> None:
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps({"voice": "xenia", "sample_rate": 24000, "threads": 3, "debug_logging": True})
    )
    args = parse_args(supervisor.options_args(options))
    assert args.data_dir == tmp_path
    assert (args.voice, args.sample_rate, args.threads, args.debug) == ("xenia", 24000, 3, True)


def test_defaults_without_options(tmp_path: Path) -> None:
    options = tmp_path / "options.json"
    options.write_text("{}")
    args = parse_args(supervisor.options_args(options))
    assert (args.voice, args.sample_rate, args.threads, args.debug) == ("baya", 48000, 2, False)


@pytest.fixture
def fake_supervisor(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    received: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append(
                {
                    "path": self.path,
                    "auth": self.headers["Authorization"],
                    "body": json.loads(body),
                }
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"result": "ok", "data": {"uuid": "x"}}')

        def log_message(self, *args: object) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(
        supervisor, "DISCOVERY_URL", f"http://127.0.0.1:{httpd.server_address[1]}/discovery"
    )
    yield received
    httpd.shutdown()


async def test_announces_once_listening(fake_supervisor: list[dict[str, Any]]) -> None:
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    await supervisor.announce("secret", port)
    server.close()
    assert fake_supervisor == [
        {
            "path": "/discovery",
            "auth": "Bearer secret",
            "body": {
                "service": "wyoming",
                "config": {"uri": f"tcp://{socket.gethostname()}:{port}"},
            },
        }
    ]


async def test_no_announcement_if_never_listening(fake_supervisor: list[dict[str, Any]]) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    await supervisor.announce("secret", port, attempts=2)
    assert fake_supervisor == []
