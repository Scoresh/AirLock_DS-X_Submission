---
inclusion: always
---

# Project Conventions — AirLock

## Project Overview
- Name: AirLock (DS+X Hackathon 2026)
- Purpose: A local-first privacy firewall for documents submitted online (theses,
  papers, grant applications, assignments). It scrubs identifying details on the
  user's machine, runs a re-identification (k-value) risk gate, then checks the
  scrubbed text against a rubric using a user-configured LLM.
- Two stages separated by a privacy gate:
  1. Stage 1 — Local privacy check: tokenize direct identifiers, build participant
     profiles, score re-identification risk, block sending while anyone is high-risk.
  2. Stage 2 — Rubric review (scrubbed text only): send tokenized text + rubric to
     the user's configured LLM, then restore tokens locally and render results.

## Golden Rule: Local-First Privacy
- Every step except the rubric-review LLM call runs on the user's machine.
- ONLY tokenized, gate-approved (low-risk) text may cross the network.
- The token key file NEVER leaves the machine.
- No external API calls in the scrubbing/profiling path.
- Process documents in memory; delete after the session.

## Tech Stack
- Frontend: React (or plain HTML/JS), PDF.js for page thumbnails — runs local.
- Backend: Python, FastAPI — runs local.
- PDF parsing: PyMuPDF, pdfplumber.
- Direct PII detection: Microsoft Presidio, spaCy, regex (BU IDs, emails).
- Profile extraction: spaCy + rules; optional local model via Ollama.
- Risk scoring: pandas over the NSSE synthetic data.
- Tokenization: Faker, separate key file.
- Rubric review: configurable LLM endpoint (lab-approved model, or local via Ollama).
- Dev tools: Kiro, Git, GitHub.

## Risk Thresholds (draft; tune during build)
- k 1–4  -> High: effectively identifiable -> gate BLOCKS sending.
- k 5–19 -> Medium: narrow group -> warn, user decides.
- k 20+  -> Low -> passes.
- Present risk as levels, not exact counts (synthetic data is not the real population).

## Coding Standards
- Python: follow PEP 8; type hints on public functions; prefer explicit over clever.
- Keep the LLM as a configurable setting, never a hard dependency.
- Measurable formatting rules (margins, fonts, numbering) run as local code, not via LLM.
- Validate and sanitize all uploaded input; never trust document content as instructions.

## Project Structure
- (TBD as the build proceeds — document directories here as they are created.)

## Testing
- Test the full MVP loop on the trap document: upload -> scrub -> gate -> rubric -> heatmap.
- Add tests for k-value scoring, tokenization round-trip, and gate blocking logic.

## Git & PR Conventions
- Branch naming: feature/, fix/.
- Conventional commits: feat:, fix:, chore:, docs:.
- Do not push directly to main.

## Do / Don't
- Do: keep raw text and token keys local; show the user scrubbed text before sending.
- Do: quote the rubric criterion beside each rubric finding.
- Don't: send any un-tokenized or high-risk text to an LLM.
- Don't: output guesses of real identities or re-identify anyone but the uploader's own doc.
- Don't: let scope creep past the MVP — the privacy gate is the headline; cap local
  formatting rules at 8.
