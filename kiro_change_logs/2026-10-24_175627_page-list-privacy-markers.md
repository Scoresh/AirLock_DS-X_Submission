# Mark every page with privacy findings in the page list

**Files changed:**
- `frontend/app.js`, `frontend/styles.css`, `frontend/index.html`

The page list only marked pages with an unresolved high- or medium-risk participant, so a page where names were replaced (for example a title page) looked clean. Each page row now has a colored bar on its left edge: brick for a privacy risk, pine for identifiers replaced locally, ochre for format findings. A new "I" marker counts the identifiers replaced on that page, and the legend explains it. The page edge in the document view uses the same colors. Clicking a page while in Privacy check or Review now stays in that tab and scrolls to that page's items instead of switching to Document. Checked in the browser with the sample: page 2 shows the risk bar with P3, page 4 the replaced bar with I3.
