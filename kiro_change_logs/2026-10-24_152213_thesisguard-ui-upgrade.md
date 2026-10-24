# ThesisGuard frontend: premium UI upgrade (navy/blue/white)

**Files changed:**
- `frontend/index.skeleton.html` (new backup of the original single-file UI)
- `frontend/index.html` (rebuilt with semantic markup, navbar, hero, stepper, cards)
- `frontend/styles.css` (new design system)
- `frontend/app.js` (new; logic extracted from the inline script)

Backed up the original `index.html` as `index.skeleton.html` before editing. Rebuilt the frontend as a modern, responsive, static site styled with a navy/blue/white palette, Inter/Source Serif typography, CSS design tokens, cards, buttons, a 4-step progress stepper, risk badges, hover/transition states, loading spinners, and an error banner. Extracted the inline CSS and JavaScript into `styles.css` and `app.js` for maintainability; no framework or build system was introduced. The full workflow is preserved: upload, privacy gate with anonymization suggestions, review heatmap with click-to-inspect findings, and the side-by-side "what the LLM saw" view. All backend integration is unchanged — same endpoints (`/parse`, `/scrub/{doc_id}`, `/score`, `/review`, `/llm-view/{doc_id}`), same request bodies, and same response field names (including the `from` alias, read as `s.from`). No backend logic or schemas were modified. Verified by serving the files and driving all five endpoints against the `/mock/*.json` payloads with a temporary stdlib server, which confirmed assets load and the gate opens after accepting suggestions; the throwaway test server was then removed.
