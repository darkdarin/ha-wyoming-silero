# Wyoming Silero: the text-to-speech server with CPU-only torch.
#
#   docker build -t wyoming-silero .
#   docker run -d -p 10200:10200 -v wyoming-silero-data:/data wyoming-silero [--voice xenia]
#
# The Silero model (CC BY-NC 4.0) is not in the image: the server downloads it into /data on first
# start. Debian, not Alpine: torch only ships glibc (manylinux) wheels. The same image runs as the
# Home Assistant app (addon/); there it reads its options from /data/options.json.

# --- Python environment, pinned by uv.lock --------------------------------------------------------
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra model --no-install-project
COPY src src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra model --no-editable

# --- runtime -------------------------------------------------------------------------------------
FROM python:3.14-slim
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    WYOMING_SILERO_DATA=/data
VOLUME /data
EXPOSE 10200
ENTRYPOINT ["wyoming-silero"]
