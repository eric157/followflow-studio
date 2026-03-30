# ─────────────────────────────────────────────────────────────────────────────
# FollowFlow Studio – Docker image
# Base: official Microsoft Playwright image (Python 3.11 + Chromium pre-installed)
# ─────────────────────────────────────────────────────────────────────────────
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Build-time caching hint for CI (BuildKit)
ARG BUILDKIT_INLINE_CACHE=1

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Dependency layer (install before copying full source for better caching) ──
# Copy only the metadata files needed by pip to resolve & install deps,
# then copy the actual source package.
COPY pyproject.toml ./
COPY src/ ./src/

# Install the package in non-editable mode so pip can locate the entry point.
# --no-cache-dir keeps the image lean.
RUN pip install --no-cache-dir --no-build-isolation .

# ── Copy remaining project files ──────────────────────────────────────────────
# .dockerignore excludes: __pycache__, .git, *.zip, build/, dist/,
#                         data/runtime/, data/processed/, .venv/, .github/
COPY . .

# ── Ensure runtime data directories exist ────────────────────────────────────
RUN mkdir -p data/exports data/processed data/runtime

# ── Environment ──────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV FOLLOWFLOW_UI_HOST=0.0.0.0
ENV FOLLOWFLOW_UI_PORT=5000

# ── Expose Review UI port ─────────────────────────────────────────────────────
EXPOSE 5000

# ── Entrypoint ───────────────────────────────────────────────────────────────
ENTRYPOINT ["followflow"]
CMD ["--help"]
