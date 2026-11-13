"""Protocol tests: Wyoming client -> wyoming-silero -> fake synthesizer."""

import asyncio

from wyoming.audio import AudioChunk, AudioStart
from wyoming.client import AsyncTcpClient
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeTextFormat,
    SynthesizeVoice,
)

from .conftest import RATE, FakeSynthesizer, fake_audio


async def read_until(client: AsyncTcpClient, *types: str) -> list[Event]:
    """Read events up to and including the first one of the given types."""
    events = []
    async with asyncio.timeout(5):
        while True:
            event = await client.read_event()
            assert event is not None, "connection closed"
            events.append(event)
            if event.type in types:
                return events


def audio_of(events: list[Event]) -> bytes:
    return b"".join(AudioChunk.from_event(e).audio for e in events if AudioChunk.is_type(e.type))


async def stream(client: AsyncTcpClient, pieces: list[str], voice: str | None = None) -> None:
    """Send text the way Home Assistant streams LLM output."""
    synth_voice = SynthesizeVoice(name=voice) if voice else None
    await client.write_event(SynthesizeStart(voice=synth_voice).event())
    for piece in pieces:
        await client.write_event(SynthesizeChunk(text=piece).event())
    await client.write_event(Synthesize(text="".join(pieces), voice=synth_voice).event())
    await client.write_event(SynthesizeStop().event())


async def test_describe(client: AsyncTcpClient) -> None:
    await client.write_event(Describe().event())
    [event] = await read_until(client, "info")
    [tts] = Info.from_event(event).tts
    assert tts.supports_synthesize_streaming is True
    assert [voice.name for voice in tts.voices] == ["aidar", "baya", "kseniya", "xenia", "eugene"]
    assert all(voice.languages == ["ru"] for voice in tts.voices)
    assert tts.description is not None and "CC BY-NC 4.0" in tts.description


async def test_synthesize_whole_text(client: AsyncTcpClient, synthesizer: FakeSynthesizer) -> None:
    await client.write_event(Synthesize(text="Привет. Сейчас 5 °C!").event())
    events = await read_until(client, "audio-stop")

    start = AudioStart.from_event(events[0])
    assert (start.rate, start.width, start.channels) == (RATE, 2, 1)
    assert synthesizer.texts == ["Привет.", "Сейчас пять градусов!"]
    assert audio_of(events) == fake_audio("Привет.") + fake_audio("Сейчас пять градусов!")
    assert [call[1] for call in synthesizer.calls] == ["baya", "baya"]


async def test_voice_choice(client: AsyncTcpClient, synthesizer: FakeSynthesizer) -> None:
    await client.write_event(Synthesize(text="Один.", voice=SynthesizeVoice("xenia")).event())
    await read_until(client, "audio-stop")
    await client.write_event(Synthesize(text="Два.", voice=SynthesizeVoice("nobody")).event())
    await read_until(client, "audio-stop")
    assert [call[1] for call in synthesizer.calls] == ["xenia", "baya"]


async def test_streaming_speaks_each_sentence_as_it_ends(
    client: AsyncTcpClient, synthesizer: FakeSynthesizer
) -> None:
    await client.write_event(SynthesizeStart().event())
    for piece in ["Первое пред", "ложение. Второе", " предложение? Тре"]:
        await client.write_event(SynthesizeChunk(text=piece).event())

    # Two sentences are complete: their audio comes before the stream ends.
    events = await read_until(client, "audio-chunk")
    events += await read_until(client, "audio-chunk")
    assert AudioStart.is_type(events[0].type)
    assert synthesizer.texts == ["Первое предложение.", "Второе предложение?"]

    await client.write_event(SynthesizeChunk(text="тье").event())
    await client.write_event(Synthesize(text="whole text, ignored").event())
    await client.write_event(SynthesizeStop().event())
    events += await read_until(client, "synthesize-stopped")

    assert synthesizer.texts == ["Первое предложение.", "Второе предложение?", "Третье."]
    types = [e.type for e in events]
    assert types.count("audio-start") == 1
    assert types[-2:] == ["audio-stop", "synthesize-stopped"]
    assert audio_of(events) == b"".join(fake_audio(t) for t in synthesizer.texts)


async def test_streaming_voice(client: AsyncTcpClient, synthesizer: FakeSynthesizer) -> None:
    await stream(client, ["Привет."], voice="aidar")
    await read_until(client, "synthesize-stopped")
    assert synthesizer.calls[0][1] == "aidar"


async def test_several_requests_on_one_connection(
    client: AsyncTcpClient, synthesizer: FakeSynthesizer
) -> None:
    for text in ["Раз.", "Два."]:
        await stream(client, [text])
        await read_until(client, "synthesize-stopped")
    await client.write_event(Synthesize(text="Три.").event())
    await read_until(client, "audio-stop")
    assert synthesizer.texts == ["Раз.", "Два.", "Три."]


async def test_english_is_not_silent(client: AsyncTcpClient, synthesizer: FakeSynthesizer) -> None:
    await stream(client, ["The lights are on."])
    events = await read_until(client, "synthesize-stopped", "error")
    assert events[-1].type == "synthesize-stopped"
    assert audio_of(events)
    assert synthesizer.texts and synthesizer.texts[0].endswith(".")


async def test_nothing_to_say_is_an_error(
    client: AsyncTcpClient, synthesizer: FakeSynthesizer
) -> None:
    await stream(client, ["👍🎉"])
    [event] = await read_until(client, "error")
    assert Error.from_event(event).code == "nothing_to_say"

    await client.write_event(Synthesize(text="   ").event())
    [event] = await read_until(client, "error")
    assert Error.from_event(event).code == "nothing_to_say"
    assert synthesizer.calls == []

    # The connection still works.
    await client.write_event(Synthesize(text="Готово.").event())
    await read_until(client, "audio-stop")


async def test_failed_sentence_is_skipped(
    client: AsyncTcpClient, synthesizer: FakeSynthesizer
) -> None:
    synthesizer.fail_on = {"Плохо."}
    await stream(client, ["Хорошо. Плохо. Снова хорошо."])
    events = await read_until(client, "synthesize-stopped", "error")
    assert events[-1].type == "synthesize-stopped"
    assert audio_of(events) == fake_audio("Хорошо.") + fake_audio("Снова хорошо.")


async def test_all_failed_is_an_error(client: AsyncTcpClient, synthesizer: FakeSynthesizer) -> None:
    synthesizer.fail_on = {"Плохо."}
    await client.write_event(Synthesize(text="Плохо.").event())
    [event] = await read_until(client, "error")
    assert Error.from_event(event).code == "synthesis_failed"


async def test_ssml_goes_to_the_model_as_is(
    client: AsyncTcpClient, synthesizer: FakeSynthesizer
) -> None:
    ssml = "<speak>Привет <break time='1s'/> мир</speak>"
    await client.write_event(Synthesize(text=ssml, text_format=SynthesizeTextFormat.SSML).event())
    events = await read_until(client, "audio-stop")
    assert synthesizer.calls == [(ssml, "baya", RATE, True)]
    assert audio_of(events) == fake_audio(ssml)


async def test_clients_share_one_synthesis_thread(port: int, synthesizer: FakeSynthesizer) -> None:
    synthesizer.delay_s = 0.05

    async def speak(text: str) -> bytes:
        async with AsyncTcpClient("127.0.0.1", port) as client:
            await stream(client, [text])
            return audio_of(await read_until(client, "synthesize-stopped"))

    first, second = await asyncio.gather(speak("Один. Два."), speak("Три. Четыре."))
    assert first == fake_audio("Один.") + fake_audio("Два.")
    assert second == fake_audio("Три.") + fake_audio("Четыре.")
    assert synthesizer.max_active == 1


async def test_disconnect_mid_stream(port: int, synthesizer: FakeSynthesizer) -> None:
    async with AsyncTcpClient("127.0.0.1", port) as client:
        await client.write_event(SynthesizeStart().event())
        await client.write_event(SynthesizeChunk(text="Начало. Обрыв").event())
        await read_until(client, "audio-chunk")
    # The server is still fine for the next client.
    async with AsyncTcpClient("127.0.0.1", port) as client:
        await client.write_event(Synthesize(text="Дальше.").event())
        await read_until(client, "audio-stop")
