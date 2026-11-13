"""Fixtures: a fake synthesizer (no torch) behind a running Wyoming server."""

import asyncio
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from wyoming.client import AsyncTcpClient

from wyoming_silero.__main__ import build_info
from wyoming_silero.handler import SileroEventHandler, TtsSettings
from wyoming_silero.synthesizer import VOICES, SynthesisError, SynthesisQueue

RATE = 24000


def fake_audio(text: str) -> bytes:
    """The fake model's "speech" for a text: its UTF-8 bytes, padded to whole samples."""
    data = text.encode()
    return data + b"\0" * (len(data) % 2)


@dataclass
class FakeSynthesizer:
    """Records what it was asked to say; fails on texts listed in `fail_on`."""

    calls: list[tuple[str, str, int, bool]] = field(default_factory=list)
    fail_on: set[str] = field(default_factory=set)
    delay_s: float = 0.0
    active: int = 0
    max_active: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def voices(self) -> tuple[str, ...]:
        return VOICES

    @property
    def texts(self) -> list[str]:
        return [call[0] for call in self.calls]

    def synthesize(self, text: str, voice: str, sample_rate: int, ssml: bool = False) -> bytes:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delay_s)
            self.calls.append((text, voice, sample_rate, ssml))
            if text in self.fail_on:
                raise SynthesisError("ValueError: ")
            return fake_audio(text)
        finally:
            with self._lock:
                self.active -= 1


@pytest.fixture
def synthesizer() -> FakeSynthesizer:
    return FakeSynthesizer()


@pytest.fixture
async def port(synthesizer: FakeSynthesizer) -> AsyncIterator[int]:
    synthesis = SynthesisQueue(synthesizer)
    info = build_info(synthesis.voices)
    settings = TtsSettings(voice="baya", sample_rate=RATE)

    async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        handler = SileroEventHandler(reader, writer, info, synthesis, settings)
        await handler.run()

    server = await asyncio.start_server(on_connect, "127.0.0.1", 0)
    yield server.sockets[0].getsockname()[1]
    server.close()
    synthesis.close()


@pytest.fixture
async def client(port: int) -> AsyncIterator[AsyncTcpClient]:
    async with AsyncTcpClient("127.0.0.1", port) as wyoming_client:
        yield wyoming_client
