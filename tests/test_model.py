"""Model download: checksum, retries, servers without Range support."""

import hashlib
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from wyoming_silero.model import ModelDownloadError, ModelFile, ensure_model

PAYLOAD = bytes(range(256)) * 16384  # 4 MB: several read chunks


class Behaviour:
    def __init__(self) -> None:
        self.requests: list[str | None] = []
        self.cut_first = False
        self.corrupt = False


@pytest.fixture
def server() -> Iterator[tuple[str, Behaviour]]:
    behaviour = Behaviour()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            # Like models.silero.ai: Range is ignored, the whole file comes back with 200.
            behaviour.requests.append(self.headers.get("Range"))
            body = PAYLOAD
            if behaviour.corrupt:
                body = b"x" + body[1:]
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if behaviour.cut_first and len(behaviour.requests) == 1:
                self.wfile.write(body[: len(body) // 2])
                return  # Content-Length promised more: the client sees a broken download
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/model.pt", behaviour
    httpd.shutdown()


def model_at(url: str) -> ModelFile:
    return ModelFile("test", url, hashlib.sha256(PAYLOAD).hexdigest(), len(PAYLOAD))


def test_downloads_and_verifies(tmp_path: Path, server: tuple[str, Behaviour]) -> None:
    url, behaviour = server
    path = ensure_model(tmp_path, model_at(url))
    assert path == tmp_path / "test.pt"
    assert path.read_bytes() == PAYLOAD
    assert not (tmp_path / "test.pt.part").exists()

    # Second start: no download.
    ensure_model(tmp_path, model_at(url))
    assert len(behaviour.requests) == 1


def test_restarts_a_broken_download(tmp_path: Path, server: tuple[str, Behaviour]) -> None:
    url, behaviour = server
    behaviour.cut_first = True
    path = ensure_model(tmp_path, model_at(url), retry_delay_s=0)
    assert path.read_bytes() == PAYLOAD
    assert behaviour.requests[0] is None
    assert behaviour.requests[1] is not None  # tried to resume, got the whole file


def test_replaces_a_corrupt_file(tmp_path: Path, server: tuple[str, Behaviour]) -> None:
    url, _ = server
    (tmp_path / "test.pt").write_bytes(b"broken")
    assert ensure_model(tmp_path, model_at(url)).read_bytes() == PAYLOAD


def test_gives_up_on_a_wrong_checksum(tmp_path: Path, server: tuple[str, Behaviour]) -> None:
    url, behaviour = server
    behaviour.corrupt = True
    with pytest.raises(ModelDownloadError):
        ensure_model(tmp_path, model_at(url), attempts=2, retry_delay_s=0)
    assert not (tmp_path / "test.pt").exists()
    assert not (tmp_path / "test.pt.part").exists()
