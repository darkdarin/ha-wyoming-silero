"""Wyoming event handler: one instance per client connection."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped,
    SynthesizeTextFormat,
    SynthesizeVoice,
)

from .synthesizer import SynthesisError, SynthesisQueue
from .text import SentenceBuffer, prepare

_LOGGER = logging.getLogger(__name__)

SAMPLE_WIDTH = 2
CHANNELS = 1
SAMPLES_PER_CHUNK = 1024

# Error codes sent to clients, so they can fall back to another voice.
NOTHING_TO_SAY = "nothing_to_say"
SYNTHESIS_FAILED = "synthesis_failed"


@dataclass(frozen=True)
class TtsSettings:
    voice: str
    sample_rate: int


class Utterance:
    """One synthesis request: sentences go in as they arrive, audio goes out in order."""

    def __init__(
        self,
        synthesis: SynthesisQueue,
        voice: str,
        sample_rate: int,
        write_event: Callable[[Event], Awaitable[None]],
    ) -> None:
        self._synthesis = synthesis
        self._voice = voice
        self._rate = sample_rate
        self._write_event = write_event
        self._buffer = SentenceBuffer()
        self._sentences: asyncio.Queue[str | None] = asyncio.Queue()
        self._worker = asyncio.create_task(self._speak())
        self._started = time.monotonic()
        self.first_audio_s: float | None = None
        self.audio_s = 0.0
        self.chars = 0
        self.failures: list[str] = []

    @property
    def spoke(self) -> bool:
        return self.first_audio_s is not None

    def add(self, text: str) -> None:
        self.chars += len(text)
        for sentence in self._buffer.add(text):
            self._sentences.put_nowait(sentence)

    async def finish(self) -> None:
        """Speak the rest of the text and wait until all audio is written."""
        for sentence in self._buffer.flush():
            self._sentences.put_nowait(sentence)
        self._sentences.put_nowait(None)
        try:
            await self._worker
        except Exception as err:
            _LOGGER.exception("Synthesis crashed")
            self.failures.append(f"{type(err).__name__}: {err}")

    async def cancel(self) -> None:
        self._worker.cancel()
        await asyncio.gather(self._worker, return_exceptions=True)

    async def _speak(self) -> None:
        while (sentence := await self._sentences.get()) is not None:
            for piece in prepare(sentence):
                try:
                    audio = await self._synthesis.synthesize(piece, self._voice, self._rate)
                except SynthesisError as err:
                    # Skip what the model cannot say instead of stopping the whole answer.
                    _LOGGER.warning("Could not synthesize %r: %s", piece, err)
                    self.failures.append(str(err))
                    continue
                await self._write_audio(audio)

    async def _write_audio(self, audio: bytes) -> None:
        if not audio:
            return
        if self.first_audio_s is None:
            self.first_audio_s = time.monotonic() - self._started
            await self._write_event(AudioStart(self._rate, SAMPLE_WIDTH, CHANNELS).event())
        self.audio_s += len(audio) / (self._rate * SAMPLE_WIDTH * CHANNELS)
        step = SAMPLES_PER_CHUNK * SAMPLE_WIDTH * CHANNELS
        for offset in range(0, len(audio), step):
            chunk = AudioChunk(self._rate, SAMPLE_WIDTH, CHANNELS, audio[offset : offset + step])
            await self._write_event(chunk.event())

    def error(self) -> Error:
        if self.failures:
            return Error(text=f"Synthesis failed: {self.failures[-1]}", code=SYNTHESIS_FAILED)
        return Error(text="No Russian text to speak", code=NOTHING_TO_SAY)

    def summary(self) -> str:
        total = time.monotonic() - self._started
        first = f"{self.first_audio_s:.2f}" if self.first_audio_s is not None else "-"
        return (
            f"{self.chars} chars -> {self.audio_s:.1f} s of audio; first audio {first} s, "
            f"done {total:.2f} s"
        )


class SileroEventHandler(AsyncEventHandler):
    """Text-to-speech, whole text or streamed. A client may send several requests in a row."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        info: Info,
        synthesis: SynthesisQueue,
        settings: TtsSettings,
    ) -> None:
        super().__init__(reader, writer)
        self._info = info
        self._synthesis = synthesis
        self._settings = settings
        self._stream: Utterance | None = None

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self._info.event())
        elif Synthesize.is_type(event.type):
            # Streaming clients send the whole text too, for servers without streaming.
            if self._stream is None:
                await self._synthesize(Synthesize.from_event(event))
        elif SynthesizeStart.is_type(event.type):
            await self._cancel_stream()
            self._stream = self._new_utterance(SynthesizeStart.from_event(event).voice)
        elif SynthesizeChunk.is_type(event.type):
            if self._stream is not None:
                self._stream.add(SynthesizeChunk.from_event(event).text)
        elif SynthesizeStop.is_type(event.type):
            await self._stop_stream()
        return True

    async def disconnect(self) -> None:
        await self._cancel_stream()

    def _resolve_voice(self, voice: SynthesizeVoice | None) -> str:
        name = voice.name if voice is not None else None
        if name in self._synthesis.voices:
            return name
        if name:
            _LOGGER.warning("Unknown voice %r, using %r", name, self._settings.voice)
        return self._settings.voice

    def _new_utterance(self, voice: SynthesizeVoice | None) -> Utterance:
        return Utterance(
            self._synthesis,
            self._resolve_voice(voice),
            self._settings.sample_rate,
            self.write_event,
        )

    async def _synthesize(self, synthesize: Synthesize) -> None:
        if synthesize.text_format == SynthesizeTextFormat.SSML:
            await self._synthesize_ssml(synthesize)
            return
        utterance = self._new_utterance(synthesize.voice)
        utterance.add(synthesize.text)
        await utterance.finish()
        if not utterance.spoke:
            _LOGGER.warning("Nothing spoken for %r", synthesize.text[:200])
            await self.write_event(utterance.error().event())
            return
        await self.write_event(AudioStop().event())
        _LOGGER.info("Synthesized %s", utterance.summary())

    async def _synthesize_ssml(self, synthesize: Synthesize) -> None:
        """SSML goes to the model as it is, in one piece."""
        voice = self._resolve_voice(synthesize.voice)
        rate = self._settings.sample_rate
        try:
            audio = await self._synthesis.synthesize(synthesize.text, voice, rate, ssml=True)
        except SynthesisError as err:
            _LOGGER.warning("Could not synthesize SSML %r: %s", synthesize.text[:200], err)
            await self.write_event(Error(text=str(err), code=SYNTHESIS_FAILED).event())
            return
        await self.write_event(AudioStart(rate, SAMPLE_WIDTH, CHANNELS).event())
        step = SAMPLES_PER_CHUNK * SAMPLE_WIDTH * CHANNELS
        for offset in range(0, len(audio), step):
            chunk = AudioChunk(rate, SAMPLE_WIDTH, CHANNELS, audio[offset : offset + step])
            await self.write_event(chunk.event())
        await self.write_event(AudioStop().event())

    async def _stop_stream(self) -> None:
        utterance, self._stream = self._stream, None
        if utterance is None:
            return
        await utterance.finish()
        if not utterance.spoke:
            _LOGGER.warning("Nothing spoken in the stream (%d chars)", utterance.chars)
            await self.write_event(utterance.error().event())
            return
        await self.write_event(AudioStop().event())
        await self.write_event(SynthesizeStopped().event())
        _LOGGER.info("Streamed %s", utterance.summary())

    async def _cancel_stream(self) -> None:
        utterance, self._stream = self._stream, None
        if utterance is not None:
            await utterance.cancel()
