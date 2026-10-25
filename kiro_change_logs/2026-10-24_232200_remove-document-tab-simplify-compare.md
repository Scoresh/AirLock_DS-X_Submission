# Remove Document tab, simplify compare toggle to "Compare"

**Files changed:**
- `frontend/index.html`
- `frontend/app.js`

Removed the "Document" inspector tab, since it largely duplicated the Privacy check tab. Dropped its tab button and `#panel-document`, removed `renderDocumentPanel` and its click listener, took "document" out of the `TABS` list, and made "Privacy check" the default/first selected tab (state init and post-load `selectTab`). The compare feature stays on the left reader column, but its toolbar toggle is simplified to read just "Compare" (and "Show document" when active) instead of the long "Compare original and prepared text" / "Show document pages" labels. To preserve the privacy-relevant scan warning that previously lived only in the Document panel, the Privacy check panel now shows a document-level notice listing any image-only (likely scanned) pages whose contents the local scrubber cannot read. Verified no dangling references to the removed tab/panel/function remain in the frontend.
