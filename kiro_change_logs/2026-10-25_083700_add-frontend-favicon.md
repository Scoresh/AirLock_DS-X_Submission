# Add icon-only favicon to frontend

**Files changed:**
- `frontend/favicon.svg` (new)
- `frontend/index.html`

Added an icon-only SVG favicon (a shield-with-keyhole privacy mark, no text) and linked it from the document head via `<link rel="icon" href="favicon.svg" type="image/svg+xml">`. The file sits in `frontend/`, which is mounted at `/` by `backend/app/main.py`, so it is served at `/favicon.svg` with a relative path. No backend changes were needed.
