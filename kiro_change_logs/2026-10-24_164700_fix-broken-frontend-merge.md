# Fix the broken frontend after merging the redesign and the heatmap overlays

**Files changed:**
- `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`

Merging Aedyn's heatmap branch into Florian's redesign interleaved two versions of `index.html`: Aedyn's inline `<script type="module">` ended up wrapped around Florian's upload, gate, review and "What the LLM saw" sections, so the browser treated that markup as code and the page showed no buttons. Restored Florian's markup and moved Aedyn's feature into `app.js`: when a PDF is uploaded, PDF.js (loaded on demand) draws the selected page in the browser and a box is overlaid for each finding that has a `bbox`; clicking a box or a finding highlights both, and findings without a box are marked "Applies to the whole page". Without an uploaded file it draws a blank Letter page. Aedyn's overlay styles were added to `styles.css` with the redesign's naming. Tested in the browser by uploading `samples/test-thesis.pdf`: k 1 → 74, gate opens, the LLM panel shows the rewritten text, and page 3 renders with its margin finding.
