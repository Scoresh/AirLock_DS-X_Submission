# Simplify configured-model status to show only the model name

**Files changed:**
- `frontend/app.js`

In `renderModelStatus()`, the configured-model branch previously read "`<model> (<endpoint>) · nothing sent yet`". Per request, the "· nothing sent yet" suffix was removed so the masthead MODEL line simply names the model in use (with its endpoint in parentheses when available). No other branches or logic changed.
