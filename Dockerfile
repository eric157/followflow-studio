# ─────────────────────────────────────────────────────────────────────────────
# Stage: runtime
# Uses the official Microsoft Playwright image (Python + Chromium pre-installed)
# ─────────────────────────────────────────────────────────────────────────────
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Build-time caching hint for CI
ARG BUILDKIT_INLINE_CACHE=1

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies FIRST (better layer caching) ──────────────────
# Copy only the files needed to resolve dependencies before copying all source.
COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# ── Copy remaining project files ──────────────────────────────────────────────
# .dockerignore ensures __pycache__, .git, *.zip, build/, dist/, data/runtime/
# etc. are never copied into this layer.
COPY . .

# ── Runtime data directories ──────────────────────────────────────────────────
RUN mkdir -p data/exports data/processed data/runtime

# ── Environment ──────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV FOLLOWFLOW_UI_HOST=0.0.0.0
ENV FOLLOWFLOW_UI_PORT=5000

# ── Expose Review UI ─────────────────────────────────────────────────────────
EXPOSE 5000

# ── Entrypoint ───────────────────────────────────────────────────────────────
ENTRYPOINT ["followflow"]
CMD ["--help"]
