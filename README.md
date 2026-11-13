<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/darkdarin/ha-wyoming-silero/main/assets/brand/dark_logo.png">
    <img alt="Wyoming Silero" src="https://raw.githubusercontent.com/darkdarin/ha-wyoming-silero/main/assets/brand/logo.png" width="420">
  </picture>
</p>

# Wyoming Silero for Home Assistant

[![Release](https://img.shields.io/github/v/release/darkdarin/ha-wyoming-silero?sort=semver)](https://github.com/darkdarin/ha-wyoming-silero/releases)
[![CI](https://github.com/darkdarin/ha-wyoming-silero/actions/workflows/ci.yml/badge.svg)](https://github.com/darkdarin/ha-wyoming-silero/actions/workflows/ci.yml)
[![Release build](https://github.com/darkdarin/ha-wyoming-silero/actions/workflows/release.yml/badge.svg)](https://github.com/darkdarin/ha-wyoming-silero/actions/workflows/release.yml)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
![aarch64](https://img.shields.io/badge/aarch64-yes-green.svg)
![amd64](https://img.shields.io/badge/amd64-yes-green.svg)
[![License](https://img.shields.io/github/license/darkdarin/ha-wyoming-silero)](LICENSE)

Russian **text-to-speech** for Home Assistant Assist that runs on your Home Assistant machine, with no
cloud: a [Wyoming](https://github.com/OHF-Voice/wyoming) server on the
[Silero](https://github.com/snakers4/silero-models) model `v5_6_ru`, packaged as a Home Assistant app.
Assist and [FlowPilot](https://github.com/darkdarin/flowpilot) speak with it like with any Wyoming voice.

> Early version (0.1). Whole and streamed text-to-speech works end to end on a Raspberry Pi 5.

> **The Silero model is licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/):
> non-commercial use only.** It is not part of this project: the app downloads it from Silero on the first
> start. The code of this project is licensed under Apache 2.0.

## What you get

- **Native Russian voices.** Five speakers of the Russian-only `v5_6_ru` model (`aidar`, `baya`, `kseniya`,
  `xenia`, `eugene`) with no accent, built-in stresses and homographs, question and exclamation intonation.
- **Fast answers on a Raspberry Pi 5.** The answer starts to sound 0.2–0.4 s after its first sentence is
  written; speech is synthesized about 15 times faster than it plays, so long answers do not stutter.
- **Streaming.** Sentences are spoken one by one while the assistant is still writing the answer.
- **Text an LLM writes.** Numbers, dates, times, temperatures and percentages are read as words; Markdown,
  links and emoji are left out; `+` stress marks and SSML pass to the model.
- **No silence.** An English answer is spoken letter by letter instead of being dropped; text with nothing to
  say gets a Wyoming error, so the client knows what happened.
- **Local.** After the model download the app works offline.

## What you need

- Home Assistant OS or Supervised, **2026.10 or newer**, on aarch64 or amd64 (for example a Raspberry Pi 5).
- About **800 MB** of free memory and 150 MB of disk for the model.
- Internet access on the first start, to download the model.

## Installation

### Step 1. Install the app

[![Open the app in Home Assistant](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=1f182efb_wyoming_silero&repository_url=https%3A%2F%2Fgithub.com%2Fdarkdarin%2Fha-wyoming-silero)

1. Press the button: Home Assistant offers to add the repository and opens the app page.
   By hand: **Settings → Apps → App Store → ⋮ → Repositories**, add
   `https://github.com/darkdarin/ha-wyoming-silero`, then find **Wyoming Silero** in the store.
2. Install the app and start it. The first start downloads the model (about 150 MB); the log says
   **Ready on tcp://0.0.0.0:10200** when the voice is ready.

### Step 2. Add the Wyoming integration

Home Assistant discovers the app by itself: confirm the **Wyoming Protocol** integration in
**Settings → Devices & services**.

### Step 3. Choose the voice

In **Settings → Voice assistants**, open your assistant, select **silero** as text-to-speech and pick a voice.

In FlowPilot, point the "Wyoming text-to-speech" node at `tcp://1f182efb-wyoming-silero:10200`.

## Configuration

| Option | Default | What it does |
| --- | --- | --- |
| **Default voice** | `baya` | Used when the client does not pick a voice. `aidar` and `eugene` are male, `baya`, `kseniya` and `xenia` are female. |
| **Sample rate** | `48000` | 8000, 24000 or 48000 Hz. The synthesis is equally fast for all three. |
| **CPU threads** | `2` | More is not faster on a Raspberry Pi 5 and takes cores from Home Assistant. |
| **Debug logging** | off | Every spoken sentence and its timing in the app log. |

### Without Home Assistant (Docker)

The app image is a plain Docker image as well:

```sh
docker run -d --name wyoming-silero -p 10200:10200 -v wyoming-silero-data:/data \
  ghcr.io/darkdarin/ha-wyoming-silero --voice xenia --sample-rate 48000 --threads 2
```

Add it in Home Assistant as a **Wyoming Protocol** integration with the host of the machine and port 10200.

## If something does not work

- **The app stops at the start with "Could not download".** The model download failed: check the internet
  connection of the Home Assistant machine and restart the app.
- **No silero in the text-to-speech list.** Check that the app is running and the Wyoming Protocol integration
  for it is added.
- **English words sound wrong.** The server only spells Latin letters out. Prepare the text before it reaches
  the server, for example with FlowPilot's "Text for speech" node.
- **A word is stressed wrong.** Put `+` before the stressed vowel in the text (`з+амок`, `зам+ок`).

## How it works

```
Assist / FlowPilot ──text (streamed)──▶ sentence buffer ──▶ text preparation ──▶ Silero v5_6_ru (torch, CPU)
        ▲                                                                              │
        └──────────────────────── audio, sentence by sentence ◀──────────────────────────┘
```

The server collects the streamed text into sentences. Each finished sentence is prepared (numbers to words,
markup and emoji out, Latin letters spelled) and synthesized on one worker thread shared by all clients, and its
audio goes back right away, while the next sentence is still being written. The model is downloaded once into
the app data, checked by its SHA-256 and warmed up before the server opens its port.

## Development

| Path | What |
| --- | --- |
| `src/wyoming_silero/` | The server: model download, synthesis queue, text preparation, Wyoming handler, app glue |
| `tests/` | Protocol and text tests on a fake synthesizer (no torch); `test_real_model.py` runs with the real model |
| `addon/` | The Home Assistant app: options, translations, docs, changelog |
| `Dockerfile` | The app image (Debian, CPU-only torch) |
| `scripts/` | `synthesize.py` (a test client with timings), `build_addon.py` (local app), `brand.py` (images), `spike.py` |

```sh
uv sync                     # without torch: enough for the tests
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
uv sync --extra model       # with torch, to run the server
uv run wyoming-silero --data-dir ~/.cache/wyoming-silero --uri tcp://127.0.0.1:10200
uv run scripts/synthesize.py "Привет! Сейчас 21 °C."
```

## License

The code is licensed under the [Apache License 2.0](LICENSE). The Silero `v5_6_ru` model, downloaded at run
time, is licensed by Silero under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
