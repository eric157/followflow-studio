# FollowFlow Studio – Docker Guide

Run FollowFlow Studio entirely inside Docker — no local Python or Playwright install needed.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (includes Compose v2)

---

## Option A – Pull from GitHub Container Registry (fastest)

```bash
# Pull the latest image
docker pull ghcr.io/eric157/followflow-studio:latest

# Verify it works
docker run --rm ghcr.io/eric157/followflow-studio:latest followflow --help

# Run a review session (Review UI → http://localhost:5000)
docker run -it \
  -v "$(pwd)/data:/app/data" \
  -p 5000:5000 \
  ghcr.io/eric157/followflow-studio:latest \
  followflow review
```

---

## Option B – Build locally with Docker Compose

```bash
# 1. Build the image
docker compose build

# 2. Start a review session (Review UI → http://localhost:5000)
docker compose up

# 3. Run other commands
docker compose run --rm followflow prepare --source scrape --username <your_username>
docker compose run --rm followflow compare
docker compose run --rm followflow extract --zip /app/data/exports/instagram-export.zip
```

---

## Persistent Data

The `data/` directory on your host is mounted to `/app/data` inside the container.

| Host path | Container path | Contents |
|---|---|---|
| `data/exports/` | `/app/data/exports/` | Instagram export ZIPs |
| `data/processed/` | `/app/data/processed/` | `followers.json`, `following.json`, `non_mutuals.json` |
| `data/runtime/` | `/app/data/runtime/` | Browser profile, review state, logs |

---

## Notes

- **Headless by default** – the container has no display. Use the Review UI at `http://localhost:5000` to make keep/unfollow decisions.
- **Instagram login** – if Instagram blocks headless login, run the app locally once to establish a browser profile in `data/runtime/browser-profile/`, then mount that directory into the container.
- **Image variants** – the Docker image is tagged `latest` (main branch) and `vX.Y.Z` (releases).

---

## Available tags on ghcr.io

| Tag | Description |
|---|---|
| `latest` | Built from the `main` branch |
| `v0.2.0` | Stable release |

```bash
docker pull ghcr.io/eric157/followflow-studio:v0.2.0
```
