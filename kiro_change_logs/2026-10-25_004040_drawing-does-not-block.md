# Page drawing no longer blocks the privacy check

**Files changed:**
- `frontend/app.js`

After a document loaded, the inspector showed "Drawing pages" and disabled every button until PDF.js finished drawing all page images. When drawing stalled (a background tab, or a slow CDN), "Apply all" and the other privacy actions could not be clicked at all. Drawing now runs in the background: progress shows above the document ("Drawing page images · 3 of 12"), controls stay enabled, and the automatic format check starts right away. If a page takes more than 8 seconds, that page and the rest show the locally extracted text instead, with a note. Starting a new document stops any drawing still in progress so old pages never appear in the new view. Checked in the browser with stalled drawing: Apply all opened the gate (k 507, 7, 42, 331, 150, 176) before any image was drawn, all 12 pages fell back to text after the timeout, and New document left no stray pages. Normal drawing in a visible window was not re-checked here.
