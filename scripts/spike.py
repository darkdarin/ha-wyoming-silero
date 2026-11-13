# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = ["torch==2.15.*", "numpy", "psutil"]
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
#
# [tool.uv.sources]
# torch = [{ index = "pytorch-cpu", marker = "sys_platform == 'linux'" }]
# ///
"""Stage 0 spike: load Silero v5_6_ru, measure speed and memory, probe awkward text.

Usage: uv run scripts/spike.py --model ~/.cache/wyoming-silero/v5_6_ru.pt [--threads 2] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np
import psutil
import torch

SHORT = "Готово, включаю свет на кухне."
SENTENCE = (
    "Сейчас на улице пасмурно, около пяти градусов тепла, к вечеру обещают небольшой дождь, "
    "так что зонт лучше взять с собой."
)
QUESTION = "Ты уже выключил утюг?"
EXCLAIM = "Какая сегодня прекрасная погода!"
HOMOGRAPH = "Замок на двери старого замка совсем заржавел."
VOICES = ["aidar", "baya", "kseniya", "xenia", "eugene"]
RATES = [8000, 24000, 48000]
AWKWARD = {
    "english": "The lights in the kitchen are now on.",
    "digits": "Температура 21,5 °C, влажность 40%, время 18:45.",
    "only_digits": "12345",
    "emoji": "Готово! 👍🎉",
    "only_emoji": "👍",
    "empty": "",
    "spaces": "   ",
    "plus_stress": "Включаю муз+ыку на ст+анции.",
    "mixed": "Включаю Spotify на колонке.",
    "long": " ".join([SENTENCE] * 12),
}


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / 1e6


def save_wav(path: Path, audio: torch.Tensor, rate: int) -> None:
    pcm = (audio.clamp(-1, 1).numpy() * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def synth(model, text: str, speaker: str, rate: int) -> tuple[torch.Tensor, float]:
    start = time.perf_counter()
    audio = model.apply_tts(text=text, speaker=speaker, sample_rate=rate)
    return audio, time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--quick", action="store_true", help="only speed for one voice")
    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    report: dict = {"torch": torch.__version__, "threads": args.threads, "rss_start_mb": rss_mb()}

    t0 = time.perf_counter()
    imp = torch.package.PackageImporter(str(args.model.expanduser()))
    model = imp.load_pickle("tts_models", "model")
    model.to(torch.device("cpu"))
    report["load_s"] = round(time.perf_counter() - t0, 2)
    report["rss_loaded_mb"] = round(rss_mb())
    report["speakers"] = list(getattr(model, "speakers", []))

    _, warm = synth(model, SHORT, "baya", 24000)
    report["warmup_s"] = round(warm, 2)
    _, warm2 = synth(model, SHORT, "baya", 24000)
    report["second_call_s"] = round(warm2, 3)

    speed = {}
    for rate in RATES:
        for name, text in [("short", SHORT), ("sentence", SENTENCE)]:
            runs = []
            for _ in range(3):
                audio, dt = synth(model, text, "baya", rate)
                runs.append(dt)
            best = min(runs)
            dur = len(audio) / rate
            speed[f"{rate}/{name}"] = {
                "synth_s": round(best, 3),
                "audio_s": round(dur, 2),
                "x_realtime": round(dur / best, 1),
            }
    report["speed"] = speed
    report["rss_after_speed_mb"] = round(rss_mb())

    if not args.quick:
        out = args.out
        if out:
            out.mkdir(parents=True, exist_ok=True)
        voices = {}
        for voice in VOICES:
            for name, text in [
                ("question", QUESTION),
                ("exclaim", EXCLAIM),
                ("homograph", HOMOGRAPH),
            ]:
                try:
                    audio, dt = synth(model, text, voice, 24000)
                    voices[f"{voice}/{name}"] = round(dt, 3)
                    if out:
                        save_wav(out / f"{voice}_{name}.wav", audio, 24000)
                except Exception as e:  # noqa: BLE001 - spike: record any failure
                    voices[f"{voice}/{name}"] = f"ERROR {type(e).__name__}: {e}"
        report["voices"] = voices

        awkward = {}
        for name, text in AWKWARD.items():
            try:
                audio, dt = synth(model, text, "baya", 24000)
                a = audio.abs()
                awkward[name] = {
                    "synth_s": round(dt, 3),
                    "audio_s": round(len(audio) / 24000, 2),
                    "peak": round(float(a.max()) if len(a) else 0.0, 3),
                }
                if out:
                    save_wav(out / f"awkward_{name}.wav", audio, 24000)
            except Exception as e:  # noqa: BLE001 - spike: record any failure
                awkward[name] = f"ERROR {type(e).__name__}: {str(e)[:200]}"
        report["awkward"] = awkward
        report["rss_end_mb"] = round(rss_mb())

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
