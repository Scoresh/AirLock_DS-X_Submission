---
# inclusion controls when this file is loaded into the agent's context.
#   always    -> loaded every session (default; can also omit frontmatter)
#   fileMatch -> only when working with matching files (excluded from auto-load)
#   manual    -> only when added via /context add
inclusion: always
---

# Project Conventions

<!--
Template steering file. Steering files are persistent rules that Kiro loads
into context automatically. Fill in the sections below and delete what you
don't need. Keep it concise — every line consumes context on every turn.
-->

## Project Overview
- Name: DS+X Hackathon 2026
- Purpose: <one-line description of what this project does>
- Tech stack: <languages, frameworks, key libraries>

## Coding Standards
- Naming: <e.g. camelCase for variables, PascalCase for types>
- Formatting: <formatter/linter to use, e.g. prettier, black, rustfmt>
- Comments: <when and how to comment>
- Error handling: <preferred patterns>

## Project Structure
- Source code lives in: <e.g. src/>
- Tests live in: <e.g. tests/>
- <any other important directories>

## Testing
- Test framework: <e.g. jest, pytest, cargo test>
- Expectation: <e.g. add tests for new features and bug fixes>
- Run tests with: <command>

## Build & Run
- Install deps: <command>
- Build: <command>
- Run locally: <command>

## Git & PR Conventions
- Branch naming: <e.g. feature/, fix/>
- Commit style: <e.g. conventional commits: feat:, fix:, chore:>
- Do not push directly to main.

## Do / Don't
- Do: <things to always do>
- Don't: <things to avoid>
