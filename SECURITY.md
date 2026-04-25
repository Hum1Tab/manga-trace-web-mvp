# Security Policy

This repository is a research/MVP implementation of per-view forensic watermark delivery for manga images.

## Important limitations

- This project does **not** prevent screenshots, DevTools downloads, screen recording, or camera capture.
- The design goal is traceability after leakage, not perfect copy prevention.
- Demo endpoints expose debug information for local verification. Do not deploy the demo configuration as-is.
- Do not embed personal information directly into images. Use short payload IDs and keep user mapping in a database.

## Before any public deployment

- Replace `MANGA_TRACE_SECRET` with a strong random secret.
- Remove debug payload/auth fields from API responses.
- Put the app behind HTTPS.
- Use a production database.
- Add proper account creation, rate limits, audit logs, and admin-only extraction tools.
- Review privacy policy, terms of service, and local law before tracking users.
