"""The real Silero model on awkward text. Slow, local only.

Runs when torch is installed (`uv sync --extra model`) and the model file is found at
$WYOMING_SILERO_MODEL (default: ~/.cache/wyoming-silero/v5_6_ru.pt).
"""

import importlib.util
import os
from pathlib import Path

import pytest

from wyoming_silero.model import V5_6_RU
from wyoming_silero.synthesizer import VOICES, SynthesisError
from wyoming_silero.text import prepare, split_sentences

MODEL = Path(
    os.environ.get("WYOMING_SILERO_MODEL", Path.home() / ".cache/wyoming-silero/v5_6_ru.pt")
)

pytestmark = [
    pytest.mark.model,
    pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="torch not installed"),
    pytest.mark.skipif(not MODEL.exists(), reason=f"no model at {MODEL}"),
]

AWKWARD = [
    "The lights in the kitchen are now on.",
    "Температура 21,5 °C, влажность 40%, время 18:45.",
    "12345",
    "Готово! 👍🎉",
    "Включаю муз+ыку на ст+анции.",
    "Включаю Spotify на колонке, USB и TV.",
    "## Итог\n- **Свет** выключен\n- Музыка: [Yandex](https://music.yandex.ru)",
    " ".join(["Сейчас на улице пасмурно, около пяти градусов тепла."] * 30),
    "Ты уже выключил утюг? Какая прекрасная погода!",
    "Он *пришёл*? Это **очень** важно!",
]


@pytest.fixture(scope="module")
def silero():  # type: ignore[no-untyped-def]
    from wyoming_silero.synthesizer import SileroSynthesizer

    return SileroSynthesizer(MODEL, threads=2)


def test_voices(silero) -> None:  # type: ignore[no-untyped-def]
    assert silero.voices == VOICES
    for voice in VOICES:
        assert len(silero.synthesize("Привет.", voice, 24000)) > 24000


@pytest.mark.parametrize("rate", [8000, 24000, 48000])
def test_rates(silero, rate: int) -> None:  # type: ignore[no-untyped-def]
    audio = silero.synthesize("Проверка частоты.", "baya", rate)
    assert 0.5 < len(audio) / 2 / rate < 3


@pytest.mark.parametrize("text", AWKWARD)
def test_prepared_text_is_spoken(silero, text: str) -> None:  # type: ignore[no-untyped-def]
    pieces = [piece for sentence in split_sentences(text) for piece in prepare(sentence)]
    assert pieces
    for piece in pieces:
        assert silero.synthesize(piece, "baya", 24000)


def test_raw_unspeakable_text_raises(silero) -> None:  # type: ignore[no-untyped-def]
    # Why the server prepares text: the bare model raises instead of speaking.
    for text in ["The lights are on.", "👍", ""]:
        with pytest.raises(SynthesisError):
            silero.synthesize(text, "baya", 24000)


def test_model_file_is_the_pinned_one() -> None:
    assert MODEL.stat().st_size == V5_6_RU.size
