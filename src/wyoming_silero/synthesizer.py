"""Speech synthesis: the Silero model and a queue that serializes access to it."""

import asyncio
import contextlib
import logging
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

_LOGGER = logging.getLogger(__name__)

VOICES = ("aidar", "baya", "kseniya", "xenia", "eugene")
SAMPLE_RATES = (8000, 24000, 48000)

# Silero fails on long input ("Model couldn't generate your text, probably it's too long") and warns
# above 1000 characters. Text is cut into pieces well below that.
MAX_INPUT_CHARS = 600

WARMUP_TEXT = "Привет, я готова."


class SynthesisError(Exception):
    """The model could not speak a piece of text."""


class Synthesizer(Protocol):
    """Turns one piece of prepared Russian text into 16-bit mono PCM. Blocking, not thread-safe."""

    @property
    def voices(self) -> tuple[str, ...]: ...

    def synthesize(self, text: str, voice: str, sample_rate: int, ssml: bool = False) -> bytes: ...


class SileroSynthesizer:
    """Silero `v5_6_ru` loaded from a torch package."""

    def __init__(self, model_path: Path, threads: int) -> None:
        import torch

        torch.set_num_threads(threads)
        with contextlib.suppress(RuntimeError):  # can only be set once per process
            torch.set_num_interop_threads(1)
        importer = torch.package.PackageImporter(str(model_path))
        with warnings.catch_warnings():
            # The model's own code has an invalid escape sequence; not ours to fix.
            warnings.simplefilter("ignore", SyntaxWarning)
            self._model: Any = importer.load_pickle("tts_models", "model")
        self._model.to(torch.device("cpu"))
        speakers = tuple(getattr(self._model, "speakers", ()))
        # A stable documented order; the model lists them differently.
        self._voices = tuple(v for v in VOICES if v in speakers) or speakers

    @property
    def voices(self) -> tuple[str, ...]:
        return self._voices

    def synthesize(self, text: str, voice: str, sample_rate: int, ssml: bool = False) -> bytes:
        import numpy as np
        import torch

        try:
            with torch.inference_mode():
                if ssml:
                    audio = self._model.apply_tts(
                        ssml_text=text, speaker=voice, sample_rate=sample_rate
                    )
                else:
                    audio = self._model.apply_tts(text=text, speaker=voice, sample_rate=sample_rate)
        except Exception as err:
            raise SynthesisError(f"{type(err).__name__}: {err}") from err
        pcm = (audio.clamp(-1.0, 1.0) * 32767.0).to(torch.int16).numpy()
        return bytes(np.ascontiguousarray(pcm).tobytes())


class SynthesisQueue:
    """Runs synthesis on one worker thread: requests from several clients wait their turn.

    Jobs are single sentences, so a long answer for one client does not block another for long.
    """

    def __init__(self, synthesizer: Synthesizer) -> None:
        self._synthesizer = synthesizer
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="silero")

    @property
    def voices(self) -> tuple[str, ...]:
        return self._synthesizer.voices

    async def synthesize(
        self, text: str, voice: str, sample_rate: int, ssml: bool = False
    ) -> bytes:
        loop = asyncio.get_running_loop()
        started = time.perf_counter()
        audio = await loop.run_in_executor(
            self._executor, self._synthesizer.synthesize, text, voice, sample_rate, ssml
        )
        _LOGGER.debug(
            "Synthesized %d chars in %.3f s: %r", len(text), time.perf_counter() - started, text
        )
        return audio

    def warm_up(self, voice: str, sample_rate: int) -> float:
        """The first call is several times slower than the rest; make it before serving."""
        started = time.perf_counter()
        self._executor.submit(
            self._synthesizer.synthesize, WARMUP_TEXT, voice, sample_rate
        ).result()
        return time.perf_counter() - started

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
