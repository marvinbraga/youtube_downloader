# syntax=docker/dockerfile:1.7

# ---- builder ----------------------------------------------------------------
# Resolves dependencies into a .venv with uv, then we copy it into a slim
# runtime image. Multi-stage keeps the final image lean (no uv binary, no
# pip cache, no apt build caches).
FROM ghcr.io/astral-sh/uv:0.5.13-python3.12-bookworm-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install only deps first — cache layer is invalidated only when lockfile changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy the project and install it (separate layer so source changes don't
# refetch every dep).
COPY app ./app
COPY web_client ./web_client
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- runtime ----------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    VIRTUAL_ENV=/app/.venv

# ffmpeg is required by yt-dlp's audio post-processor (m4a/mp3 extraction).
# nodejs is detected by app/services/downloaders/youtube.py to solve YouTube
# JS player challenges (js_runtimes={"node": {"path": ...}}). Without it,
# the app boots with a warning and YouTube downloads may fail.
# tini gives us a proper PID 1 with signal forwarding so SIGTERM from
# `docker stop` is delivered cleanly to uvicorn.
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
        ffmpeg \
        nodejs \
        tini \
        curl \
 && rm -rf /var/lib/apt/lists/*

# Non-root user. UID 1000 matches the typical host user, which makes
# bind-mounted volumes (./data, ./downloads) writable without chown gymnastics.
RUN groupadd --system --gid 1000 app \
 && useradd  --system --uid 1000 --gid app --home-dir /app --shell /sbin/nologin app \
 && mkdir -p /app/data /app/downloads/audio /app/downloads/videos \
 && chown -R app:app /app

WORKDIR /app

# Bring in the resolved venv and project sources from the builder.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app app ./app
COPY --chown=app:app web_client ./web_client
COPY --chown=app:app pyproject.toml README.md ./

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/ > /dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.uwtv.main:app", "--host", "0.0.0.0", "--port", "8000"]
