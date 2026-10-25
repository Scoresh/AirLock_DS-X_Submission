# Restyle the full rubric scene (panel, load card, empty state)

**Files changed:**
- `frontend/app.js`
- `frontend/styles.css`

Extended the earlier rubric table restyle to the whole rubric panel. `renderRubricPanel()` now wraps all three branches (error, no-rubric, loaded) in a `rubric-scene` container with a `panel__head` header; the loaded view shows a pill criterion count. The load controls are framed as a soft inset card with a leading document glyph (`rubric-load`), and the "no rubric loaded" state is a centered dashed-border placeholder with an icon, title and hint (`rubric-empty`) instead of a bare line of text. The action bar gained a top divider and consistent spacing (`rubric-actions`). All existing IDs (`rubric-raw`, `rubric-file`), `data-action` buttons, and the `rubric__tablewrap` hook are preserved, so the delegated change/click handlers and the popout still work. New CSS was scoped under the rubric-specific classes so other panels are unaffected. No rubric JSON-loading or check logic changed. Node is not installed in this environment, so the JS was verified by review rather than a syntax checker.
