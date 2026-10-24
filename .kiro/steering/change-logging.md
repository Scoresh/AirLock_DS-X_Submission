---
inclusion: always
---

# Change Logging

After completing any code change (creating or editing files), write a summary
to the `kiro_change_logs/` directory in the project root.

Rules:
- The summary MUST be at most 10 sentences describing what was changed and why.
- Create one new file per logical change. Do NOT overwrite existing logs.
- Name each file `YYYY-MM-DD_HHMMSS_<short-kebab-title>.md`
  (e.g. `2026-10-24_132700_add-login-endpoint.md`).
- Create the `kiro_change_logs/` directory if it does not exist.
- Each log file should contain:
  - A `# Title` line
  - A `**Files changed:**` list
  - The summary (up to 10 sentences) as a single paragraph or bullet list.
