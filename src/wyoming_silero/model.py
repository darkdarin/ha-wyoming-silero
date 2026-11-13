"""Download of the Silero model into the data directory, pinned by SHA-256."""

import hashlib
import http.client
import logging
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

CHUNK_SIZE = 1 << 20


@dataclass(frozen=True)
class ModelFile:
    """A model file published by Silero."""

    name: str
    url: str
    sha256: str
    size: int


# https://github.com/snakers4/silero-models/blob/master/models.yml
# License: CC BY-NC 4.0. Downloaded by the user's server, never shipped with this project.
V5_6_RU = ModelFile(
    name="v5_6_ru",
    url="https://models.silero.ai/models/tts/ru/v5_6_ru.pt",
    sha256="04cc9b1d08ce38bcaa9d02c488d80d3e6806d17f7eaa7c95982f36a3cbf50b2e",
    size=147_664_410,
)


class ModelDownloadError(Exception):
    """The model could not be downloaded or did not match its checksum."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch(model: ModelFile, part: Path, timeout_s: float) -> None:
    """Download into `part`, continuing it if the server honours a Range request."""
    offset = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(model.url, headers={"User-Agent": "wyoming-silero"})
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        if offset and response.status != 206:
            # models.silero.ai ignores Range and sends the whole file again.
            _LOGGER.info("The server cannot resume, downloading from the start")
            offset = 0
        total = offset + int(response.headers.get("Content-Length") or 0)
        logged = 0
        with part.open("ab" if offset else "wb") as file:
            while chunk := response.read(CHUNK_SIZE):
                file.write(chunk)
                offset += len(chunk)
                if total and offset - logged >= total // 10:
                    logged = offset
                    _LOGGER.info("Downloading the model: %d%%", offset * 100 // total)
    if total and offset < total:
        # Keep the part: the next attempt continues it where the server allows.
        raise ConnectionError(f"download cut at {offset} of {total} bytes")


def ensure_model(
    data_dir: Path,
    model: ModelFile = V5_6_RU,
    attempts: int = 5,
    retry_delay_s: float = 5.0,
    timeout_s: float = 60.0,
) -> Path:
    """Return the path of the verified model file, downloading it on first use."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{model.name}.pt"
    if path.exists():
        if file_sha256(path) == model.sha256:
            return path
        _LOGGER.warning("%s does not match its checksum, downloading it again", path)
        path.unlink()

    part = path.with_suffix(".pt.part")
    _LOGGER.info(
        "Downloading the Silero model %s (%d MB, CC BY-NC 4.0) from %s",
        model.name,
        model.size // 1_000_000,
        model.url,
    )
    for attempt in range(1, attempts + 1):
        try:
            _fetch(model, part, timeout_s)
        except (OSError, http.client.HTTPException) as err:
            _LOGGER.warning("Model download failed (attempt %d of %d): %s", attempt, attempts, err)
            if attempt < attempts:
                time.sleep(retry_delay_s * attempt)
            continue
        if file_sha256(part) == model.sha256:
            part.replace(path)
            _LOGGER.info("Model saved to %s", path)
            return path
        _LOGGER.warning(
            "Downloaded model does not match its checksum (attempt %d of %d)", attempt, attempts
        )
        part.unlink()
    raise ModelDownloadError(f"Could not download {model.url}")
