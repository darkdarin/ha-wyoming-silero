# Changelog

Each version has two parts. **Server** is wyoming-silero itself: it runs inside the Home Assistant app and in
the Docker image, and changes there affect every installation. **App** is the Home Assistant packaging: options,
installation, discovery. If a part did not change, it says so.

## 0.1.0

### Server

- First version: Russian text-to-speech with the Silero `v5_6_ru` model and its five voices, whole text or
  streamed sentence by sentence while the assistant is still writing.
- Numbers, dates, times, temperatures and percentages are read as words; Markdown, links and emoji are left
  out; Latin letters are spoken letter by letter; `+` stress marks and SSML pass through.
- Text with nothing to say gets a Wyoming error instead of silence.
- The model (CC BY-NC 4.0) is downloaded on the first start and checked by its SHA-256.

### App

- First version: voice, sample rate and CPU threads options in English and Russian; Home Assistant discovers
  the app by itself; the model stays out of backups.
