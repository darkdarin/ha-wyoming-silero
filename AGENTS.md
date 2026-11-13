# AGENTS.md

**wyoming-silero** is a [Wyoming](https://github.com/OHF-Voice/wyoming) text-to-speech server on the Russian
[Silero](https://github.com/snakers4/silero-models) model `v5_6_ru` (voices `aidar`, `baya`, `kseniya`, `xenia`,
`eugene`), shipped as a Home Assistant app. It runs locally on the CPU (Raspberry Pi 5 and amd64), with no cloud.
Clients: Home Assistant Assist and [FlowPilot](https://github.com/darkdarin/flowpilot) (its "Wyoming text-to-speech"
node, streaming mode).

Why our own: the Silero app in the owner's house (`ganiushin/parakeet-stt-silero-tts-addons-haos`) speaks with the
multilingual `v5_cis_base` voices (an accent, stresses from a separate `silero-stress`). `v5_6_ru` (October 2026) is
Russian-only: no accent, built-in stresses and homographs, question and exclamation intonation. No ready Home
Assistant app with it exists for the Pi.

## Status

The Wyoming server works on the Mac (stages 1–3 of the roadmap: server, text preparation, tests). Not done yet:
the spike measurements on the Pi, the Home Assistant app (stage 4), the check on the Pi. Python is 3.14 (torch
2.15 has CPU wheels for it on aarch64 and amd64; Linux needs a glibc base image, not Alpine).

## Layout and commands

| Path | What |
| --- | --- |
| `src/wyoming_silero/model.py` | Model download into the data dir, SHA-256 pinned. `models.silero.ai` ignores `Range`: a broken download starts over |
| `src/wyoming_silero/synthesizer.py` | `SileroSynthesizer` (torch, imported lazily) and `SynthesisQueue` (one worker thread for all clients) |
| `src/wyoming_silero/text.py` | Text preparation (Markdown, emoji, numbers, Latin fallback) and the sentence buffer for streaming |
| `src/wyoming_silero/handler.py` | Wyoming events; nothing to say → `error` with code `nothing_to_say` / `synthesis_failed` |
| `tests/` | Fake synthesizer, no torch; `test_real_model.py` runs only with torch and a local model |
| `scripts/synthesize.py` | Client that streams text like HA and prints `first_audio_ms` / `done_ms` / `realtime` |
| `scripts/spike.py` | Stage 0 measurements of the bare model (self-contained `uv run` script) |

- `uv sync` (no torch) → `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`.
- `uv sync --extra model` adds torch and numpy; the model lives in `~/.cache/wyoming-silero/` locally
  (`uv run python -m wyoming_silero --data-dir ~/.cache/wyoming-silero`).

## Documentation (read before working)

Development notes, requirements and research live in Notion, in Russian (workspace darkdarin; use the personal Notion
MCP, never the work one), page [Wyoming Silero](https://app.notion.com/p/417e74ee720f8182b794ef2a38b74383):

- [Требования](https://app.notion.com/p/417e74ee720f8101a196d53e37db91db) — what the server and the app must do for
  0.1.0, speed and memory targets for the Pi 5, what is out of scope
- [Roadmap](https://app.notion.com/p/417e74ee720f81aa857be6e2a9d4f7a6) — stages and what is done; tick items there
  as they get done
- [Исследование](https://app.notion.com/p/417e74ee720f8115a50ed5f7d2906d00) — Silero model lines and licenses,
  ready-made servers, decisions taken

How the family of projects ships to Home Assistant (repository layout, README style, branding, app image, changelog,
releases, CI) is one shared page: [Поставка в Home Assistant](https://app.notion.com/p/410e74ee720f81f184cfc6ecf07080ba).
Follow its "repository with an app only" variant. Update that page when you learn a new shipping lesson.

The closest example of this kind of project is the sibling repository `~/Projects/ha-wyoming-soniox` (a Wyoming
server plus a Home Assistant app, prebuilt image in ghcr, `### Server` / `### App` changelog). The main client is
`~/Projects/ha-flow-pilot` (FlowPilot); its live debug "Timeline" shows `first_audio_ms`, `done_ms` and `realtime`
of every TTS node, which is how speed is measured end to end.

## Rules

- **The model license is CC BY-NC 4.0 (non-commercial).** Never commit the model or put it in the image: the app
  downloads it on first start into its data directory (SHA-256 pinned, resumable). README and DOCS say so plainly.
  The code is Apache-2.0, like the rest of the family. Only Silero's base CIS models are MIT; we do not use them.
- Everything in the repository is in **English**: code, identifiers, comments, docstrings, README, commit messages.
  User-facing texts of the app have English and Russian translations. Research and plans go to Notion, in Russian.
- Python with `uv`; the Python version is the one that has CPU wheels of torch for aarch64 (decided in the spike).
  Checks: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest`. Protocol and text tests run on a fake
  synthesizer, without torch; the real model is a separate slow test run locally.
- **Do not go silent.** Text the model cannot say (English, only digits, emoji, empty) must not end in silence or a
  hang: transliterate as a fallback or answer with an explicit Wyoming `error` so the client can fall back. This
  comes from a real bug: an English answer on the current Silero left the Station silent and stopped the music.
- CI must be fast: no `apt-get install` in test jobs. The image builds for amd64 and arm64 on native runners
  (no QEMU).
- Do not mark a feature done without an end-to-end check on the owner's Pi: FlowPilot → this server → the Station,
  with measurements in FlowPilot's Timeline.

## Repository and access

- GitHub: `darkdarin/ha-wyoming-silero` — **not created yet; create it only when the owner asks.** Push over SSH.
- The global `gh` account is a work account; never run `gh auth switch`. Use the personal account per command:
  `GH_TOKEN="$(gh auth token --user darkdarin)" gh …`, and never print the token.
- Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `ci:`), without AI attribution lines;
  the personal git author is configured locally in the repository. Green, finished steps may be committed and pushed
  to `main` without asking; creating the repository, releases and publishing only on the owner's request.
- The owner's live Home Assistant (Raspberry Pi 5, `ssh ha`) is a real home: installing or restarting apps, changing
  devices or the FlowPilot graph there only with the owner's consent for each action.
- Never commit secrets, tokens, models or voice recordings; never read `.env` / `.envrc` files with secrets.
