# Wyoming Silero

Local Russian text-to-speech for Home Assistant Assist with the [Silero](https://github.com/snakers4/silero-models)
model `v5_6_ru`, over the Wyoming protocol. Everything runs on the processor of your Home Assistant machine.

## Model license

The `v5_6_ru` model is made by Silero and licensed under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/): **non-commercial use only**. It is not part of
this app. On the first start the app downloads it from `models.silero.ai` (about 150 MB), checks its SHA-256
and keeps it in the app data; it is left out of backups and downloaded again after a restore. By using the app
you accept the model license. The app code is licensed under Apache 2.0.

## Setup

1. Start the app. The first start downloads the model, so it needs internet access once; after that the app
   works offline. The log shows the progress; the voice is ready after **Ready on tcp://0.0.0.0:10200**.
2. Home Assistant discovers the app: confirm the **Wyoming Protocol** integration.
3. In **Settings → Voice assistants**, select **silero** as text-to-speech of your assistant and pick a voice.

FlowPilot and other apps reach the server inside Home Assistant at `tcp://1f182efb-wyoming-silero:10200`.

## Options

| Option | What it does |
| --- | --- |
| **Default voice** | Used when the assistant does not pick a voice. `aidar` and `eugene` are male, `baya`, `kseniya` and `xenia` are female. |
| **Sample rate** | 8000, 24000 or 48000 Hz. The synthesis is equally fast for all three. |
| **CPU threads** | 2 by default. More is not faster on a Raspberry Pi 5 and takes cores from Home Assistant. |
| **Debug logging** | Every spoken sentence and its timing in the app log. |

## What it does with the text

The model speaks Russian text only, so the app prepares answers before speaking them:

- numbers, times, dates, temperatures, percentages and some units become words: `21,5 °C` is read as
  "двадцать одна целая пять десятых градуса", `18:45` as "восемнадцать сорок пять";
- Markdown, links and emoji are left out; list items and headings are read as separate sentences;
- Latin letters are spoken letter by letter (`USB` → "ю эс би") so an English answer is not silently dropped.
  For proper English pronunciation, prepare the text before it reaches the app (FlowPilot's "Text for speech"
  node does this);
- a `+` before a vowel marks the stress (`з+амок`, `зам+ок`) and is passed to the model as is;
- SSML (`<speak>…</speak>`) sent with the SSML text format goes to the model unchanged.

If there is nothing to say (only emoji, an empty text), the app answers with a Wyoming error instead of silence,
so the client can tell what happened.

## Speed and memory

On a Raspberry Pi 5 the first sound of an answer comes 0.2–0.4 s after its first sentence ends, and speech is
synthesized about 15 times faster than it plays. A long first sentence takes longer (about 0.8 s for 160
characters). The app uses about 800 MB of memory.

## If something does not work

- **The app stops at the start with "Could not download".** The model download failed: check the internet
  connection of your Home Assistant machine and restart the app.
- **No silero in the text-to-speech list.** Check that the app is running and the Wyoming Protocol integration
  for it is added (**Settings → Devices & services**).
- **A word is stressed wrong.** Mark the stress with `+` before the vowel in the text you send, or report the
  word to [Silero](https://github.com/snakers4/silero-models/issues).
