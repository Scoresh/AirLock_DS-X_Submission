# Move Compare to the left column, remove the Review tab

**Files changed:**
- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`

Moved the "Compare" toggle out of the top-right toolbar into a new `.reader__bar` at the top of the left reader column, so it sits beside the document it compares. Removed the "Review" inspector tab entirely: dropped its tab button and `#panel-review`, removed `renderReviewPanel` and its listener, and took "review" out of the `TABS` list. To keep the review workflow intact, review findings now render inside the Privacy check panel via a new `reviewFindingsHtml()` helper appended after the gate, and the gate's "Send prepared text for review" button (in `gateHtml`, already shown in the Privacy panel) still starts a review. Rewired the places that assumed a Review tab/panel: the inspector delegated click handler now opens finding annotations (`.annot[data-key]`), `runReview` lands back on the Privacy tab and scrolls to the findings, the heatmap finding click selects the Privacy tab, and the removed `count-review` badge was deleted. Added `.reader__bar` styling for the relocated Compare button. No backend or data-contract changes.
