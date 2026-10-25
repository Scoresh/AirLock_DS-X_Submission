# Rubric gets its own full-width tab

**Files changed:**
- `frontend/app.js`
- `frontend/styles.css`

Moved the Rubric tab out of the cramped right-hand inspector column so it spans the full workspace width. Added a `FULL_WIDTH_TABS` list in `selectTab` that sets `data-full="1"` on `.workspace__grid` when the Rubric tab is active and clears it otherwise. Added CSS so that in full mode the grid collapses to a single column, the sidebar and reader are hidden, and the inspector (which holds the rubric panel) takes the whole width with no left border. Also hid the narrow-screen Document/Findings pane toggle while a full-width tab is active, since the reader is hidden there and the toggle would be misleading. Switching to any other tab restores the normal three-column layout. No backend or data-contract changes.
