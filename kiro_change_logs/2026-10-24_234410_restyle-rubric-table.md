# Restyle rubric table and verdict badges

**Files changed:**
- `frontend/styles.css`
- `frontend/app.js`

The rubric section looked plain, so the table and verdict styling were upgraded to match the editorial paper palette. The table is now wrapped in a rounded, shadowed card with a sticky uppercase header, zebra striping, and row hover. Each row gets a coloured left accent on its title cell reflecting the verdict (green fulfilled, brick not-fulfilled, ochre not-enough-info), driven by a new `is-yes` / `is-no` / `is-info` class added in `rubricTableHtml()`. Verdict pills gained a leading status dot and subtle tinted borders, and the `verdict--info` colour now uses the existing `--ochre` tokens instead of an undefined `--gold` fallback. The rubric source label is now a small pill. No rubric JSON-loading or check logic was changed.
