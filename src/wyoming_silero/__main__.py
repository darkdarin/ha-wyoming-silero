"""Command line entry point."""

import argparse
import asyncio
import logging
import os
import sys
import time
from functools import partial
from pathlib import Path
from urllib.parse import urlparse

from wyoming.info import Attribution, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncServer

from . import __version__
from .handler import SileroEventHandler, TtsSettings
from .model import V5_6_RU, ModelDownloadError, ensure_model
from .supervisor import OPTIONS_PATH, announce, options_args, supervisor_token
from .synthesizer import SAMPLE_RATES, VOICES, SynthesisQueue, Synthesizer

_LOGGER = logging.getLogger(__name__)

SILERO_ATTRIBUTION = Attribution(name="Silero", url="https://github.com/snakers4/silero-models")


def build_info(voices: tuple[str, ...]) -> Info:
    return Info(
        tts=[
            TtsProgram(
                name="silero",
                description=f"Silero {V5_6_RU.name} (model license CC BY-NC 4.0)",
                attribution=SILERO_ATTRIBUTION,
                installed=True,
                version=__version__,
                voices=[
                    TtsVoice(
                        name=voice,
                        description=f"{voice} ({V5_6_RU.name})",
                        attribution=SILERO_ATTRIBUTION,
                        installed=True,
                        version=None,
                        languages=["ru"],
                    )
                    for voice in voices
                ],
                supports_synthesize_streaming=True,
            )
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="wyoming-silero", description=__doc__)
    parser.add_argument("--uri", default="tcp://0.0.0.0:10200", help="unix:// or tcp://")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("WYOMING_SILERO_DATA", "/data")),
        help="Where the model is downloaded (default: $WYOMING_SILERO_DATA or /data)",
    )
    parser.add_argument("--voice", choices=VOICES, default="baya", help="Default voice")
    parser.add_argument("--sample-rate", type=int, choices=SAMPLE_RATES, default=48000)
    parser.add_argument("--threads", type=int, default=2, help="torch CPU threads")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args(argv)


def load_synthesizer(data_dir: Path, threads: int) -> Synthesizer:
    from .synthesizer import SileroSynthesizer

    model_path = ensure_model(data_dir)
    started = time.perf_counter()
    synthesizer = SileroSynthesizer(model_path, threads)
    _LOGGER.info("Model loaded in %.1f s", time.perf_counter() - started)
    return synthesizer


async def serve(uri: str, synthesis: SynthesisQueue, settings: TtsSettings) -> None:
    server = AsyncServer.from_uri(uri)
    info = build_info(synthesis.voices)
    _LOGGER.info("Ready on %s (voice %s, %d Hz)", uri, settings.voice, settings.sample_rate)
    token = supervisor_token()
    port = urlparse(uri).port
    if token and port:
        discovery = asyncio.create_task(announce(token, port))
    try:
        await server.run(
            partial(SileroEventHandler, info=info, synthesis=synthesis, settings=settings)
        )
    finally:
        if token and port:
            discovery.cancel()


def main() -> None:
    argv = sys.argv[1:]
    if supervisor_token() and OPTIONS_PATH.exists():
        # A Home Assistant app: the options page decides, extra arguments still win.
        argv = options_args() + argv
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        synthesizer = load_synthesizer(args.data_dir, args.threads)
    except ModelDownloadError as err:
        _LOGGER.error("%s; check the internet connection and restart", err)
        sys.exit(1)
    synthesis = SynthesisQueue(synthesizer)
    # The port opens only after the warm-up, so the first real request is fast.
    warm_up_s = synthesis.warm_up(args.voice, args.sample_rate)
    _LOGGER.info("Warmed up in %.2f s", warm_up_s)
    settings = TtsSettings(voice=args.voice, sample_rate=args.sample_rate)
    try:
        asyncio.run(serve(args.uri, synthesis, settings))
    except KeyboardInterrupt:
        pass
    finally:
        synthesis.close()


if __name__ == "__main__":
    main()
