# MangaTrace Web MVP

English | [日本語](README.ja.md)

MangaTrace Web MVP is a minimal FastAPI + SQLite + Pillow prototype for serving per-view, low-visibility forensic-watermarked manga images.

The goal is **not** to make images impossible to save. Once an image is displayed in a browser, it can be copied through DevTools, screenshots, screen recording, or a camera. The goal is to ensure that the image returned to the browser is already watermarked with a short per-view payload that can later be mapped back to a database record.

## What this MVP does

- Logs in a demo user.
- Lists demo manga pages.
- Creates a `view_id` every time a page is opened.
- Generates `payload_id`, `auth_tag`, and `seed` for that view.
- Stores the mapping in SQLite.
- Renders a watermarked image from a non-public base image.
- Returns only `/api/views/{view_id}/image` to the browser.
- Provides a CLI extraction helper for local verification.

## What this MVP does not do

- It does not prevent screenshots or DevTools downloads.
- It does not include production account management.
- It does not include payment, DRM, CDN, S3/R2, Redis, or an admin panel.
- It does not implement robust blind extraction, ECC, or production-grade mask selection yet.
- It is not legal advice and is not ready for production deployment as-is.

## Repository structure

```text
manga_trace_web_mvp/
  backend/app/
    main.py        FastAPI app and API routes
    db.py          SQLite schema and connection helper
    watermark.py   watermark embed/extract logic
    security.py    password hashing and HMAC helper
    config.py      paths and environment config
  frontend/
    login.html
    viewer.html
  scripts/
    init_demo.py   creates demo DB and demo pages
  tools/
    extract_saved_image.py
  docs/
    WEB_MVP_NOTES.md
    PUBLIC_RELEASE_CHECKLIST.md
  data/
    .gitkeep       runtime DB/images are generated locally and ignored by git
```

## Setup

```bash
git clone https://github.com/Hum1Tab/manga-trace-web-mvp.git
cd manga-trace-web-mvp
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies and initialize demo data:

```bash
pip install -r requirements.txt
python scripts/init_demo.py
```

Start the server:

```bash
uvicorn backend.app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

Demo login:

```text
demo@example.com
password
```

## Environment variables

Copy `.env.example` to `.env` for local use if needed:

```bash
cp .env.example .env
```

Set a real secret before any non-local use:

```text
MANGA_TRACE_SECRET=replace-with-a-long-random-secret
```

The app falls back to a development secret if the variable is not set. That is acceptable only for local tests.

## Web flow

```text
User logs in
  ↓
Frontend calls POST /api/views with page_id
  ↓
Server creates view_id, payload_id, auth_tag, seed
  ↓
Server stores the mapping in SQLite
  ↓
Frontend displays /api/views/{view_id}/image
  ↓
Server reads internal base image and returns a watermarked WebP
```

The original/base image is not exposed as a static file. If someone saves the browser image, they save the watermarked version.

## API

```http
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
GET  /api/pages
POST /api/views
GET  /api/views/{view_id}/image
GET  /api/views/{view_id}  # debug endpoint for MVP only
```

## Extract a saved image locally

The current MVP extractor is non-blind: it needs the original base image and the view seed. The seed is exposed by the debug endpoint only for local testing.

Example:

```bash
python tools/extract_saved_image.py data/pages/page_001/base.png saved_watermarked.webp --seed SEED_FROM_DEBUG_JSON
```

## GitHub publish checklist

Before pushing publicly:

- Keep `.env` out of git.
- Keep `data/app.db` out of git.
- Do not commit real manga pages.
- Do not commit real user data.
- Do not commit extraction cases or investigation outputs.

Publish:

```bash
git init
git add .
git commit -m "Initial MangaTrace Web MVP"
git branch -M main
git remote add origin https://github.com/Hum1Tab/manga-trace-web-mvp.git
git push -u origin main
```

## Production hardening notes

Before any real deployment:

- Remove `debug_payload_id`, `debug_auth_tag`, and seed exposure from user-facing APIs.
- Move extraction tools behind admin-only access.
- Use HTTPS.
- Use PostgreSQL instead of local SQLite.
- Add rate limits and audit logs.
- Use private object storage for base images.
- Add proper cache rules: `Cache-Control: no-store, private` for user-specific images.
- Add terms/privacy notice explaining that anti-leak tracing information may be embedded.
- Keep extracted results as candidates with confidence, not absolute proof.

## License

MIT License. See [LICENSE](LICENSE).
