# Heatmap Level 2: page thumbnails with bbox overlays

**Files changed:**
- backend/app/schemas.py
- mock/review.json
- frontend/index.html

Added a `BBox` model and an optional `bbox: list[BBox]` field to `Finding` so a
finding can point at one or more regions on a page (a quote that wraps across
lines yields one box per line; an empty list means a page-level finding). This is
an additive, backward-compatible contract change agreed with the team, and the
matching `mock/review.json` was updated in the same change with example boxes
covering the single-box, multi-box, and no-box cases. The frontend heatmap was
upgraded from a page-tile grid (Level 1) to a Level 2 view: it loads PDF.js and
opens the uploaded PDF locally (the file never leaves the machine), renders each
flagged page to a canvas, and overlays severity-colored boxes positioned by
scaling bbox PDF points to the rendered pixel width. Findings without a box render
as whole-page badges, and clicking a box or its list entry cross-highlights the
pair. When no real PDF is available (mock run) it draws a blank page at the
correct aspect ratio so boxes still land. Bbox coordinates in the mock are
hand-estimated placeholders; pixel-accurate boxes arrive once format_rules.py and
review.py populate them from real layout and PyMuPDF quote search.
