"""Speak text through a running wyoming-silero server, the way Home Assistant streams it.

Usage: uv run scripts/synthesize.py [--uri tcp://127.0.0.1:10200] [--voice baya] [--whole]
                                    [--out speech.wav] "Text to say"
Prints the time to the first audio, the total time and the speed against real time.
"""

import argparse
import asyncio
import time
import wave

from wyoming.audio import AudioChunk, AudioStart
from wyoming.client import AsyncClient
from wyoming.error import Error
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped,
    SynthesizeVoice,
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--uri", default="tcp://127.0.0.1:10200")
    parser.add_argument("--voice", default=None)
    parser.add_argument("--whole", action="store_true", help="one synthesize event, no streaming")
    parser.add_argument("--chunk-chars", type=int, default=8, help="streamed piece size")
    parser.add_argument("--out", default=None, help="save the audio as WAV")
    args = parser.parse_args()

    voice = SynthesizeVoice(name=args.voice) if args.voice else None
    audio = bytearray()
    rate = 0
    first_audio: float | None = None
    async with AsyncClient.from_uri(args.uri) as client:
        started = time.perf_counter()
        if args.whole:
            await client.write_event(Synthesize(text=args.text, voice=voice).event())
        else:
            await client.write_event(SynthesizeStart(voice=voice).event())
            for i in range(0, len(args.text), args.chunk_chars):
                piece = args.text[i : i + args.chunk_chars]
                await client.write_event(SynthesizeChunk(text=piece).event())
            await client.write_event(Synthesize(text=args.text, voice=voice).event())
            await client.write_event(SynthesizeStop().event())
        while event := await client.read_event():
            if Error.is_type(event.type):
                error = Error.from_event(event)
                print(f"error {error.code}: {error.text}")
                return
            if AudioStart.is_type(event.type):
                rate = AudioStart.from_event(event).rate
            elif AudioChunk.is_type(event.type):
                if first_audio is None:
                    first_audio = time.perf_counter() - started
                audio += AudioChunk.from_event(event).audio
            elif event.type == "audio-stop" and args.whole:
                break
            elif SynthesizeStopped.is_type(event.type):
                break
        done = time.perf_counter() - started

    seconds = len(audio) / 2 / rate if rate else 0.0
    first = f"{first_audio * 1000:.0f}" if first_audio is not None else "-"
    print(
        f"first_audio_ms={first} done_ms={done * 1000:.0f} audio_s={seconds:.2f} "
        f"realtime={seconds / done:.1f}x"
    )
    if args.out and rate:
        with wave.open(args.out, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(bytes(audio))


if __name__ == "__main__":
    asyncio.run(main())
