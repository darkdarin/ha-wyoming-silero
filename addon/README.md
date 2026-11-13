# Wyoming Silero

Local Russian **text-to-speech** for Home Assistant Assist with the
[Silero](https://github.com/snakers4/silero-models) model `v5_6_ru`. Runs on the processor of your Home
Assistant machine (Raspberry Pi 5 or amd64), with no cloud.

## Features

- Five native Russian voices: `aidar`, `baya`, `kseniya`, `xenia`, `eugene`.
- Stresses, homographs, questions and exclamations right out of the model.
- Spoken answers start while the assistant is still writing them: about 0.2–0.4 s on a Raspberry Pi 5.
- Numbers, dates, temperatures, Markdown and emoji in assistant answers are read as words or left out; an
  English answer is spoken letter by letter instead of leaving the speaker silent.

## Getting started

1. Start the app. The first start downloads the Silero model (about 150 MB).
2. Confirm the discovered **Wyoming Protocol** integration.
3. Select **silero** as text-to-speech of your voice assistant and pick a voice.

**The Silero model is licensed under CC BY-NC 4.0: non-commercial use only.** Details are on the
**Documentation** tab and in the [project README](https://github.com/darkdarin/ha-wyoming-silero).
