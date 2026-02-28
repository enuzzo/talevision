# .codex — TaleVision Private Agent Memory (Codex CLI)

This folder contains **private, local, non-versioned** working memory for Codex CLI sessions.

Public, stable project knowledge lives in `knowledge/` (versioned, provider-agnostic).

## Structure

- **MEMORY.md** — Local private rules and session context. Short. Updated only when stable.
- **SESSION_LOG.md** — Append-only session diary. One entry per session. Never delete entries.
- **README.md** — This file.

## Session Ritual

**Start of session:**
1. Read `knowledge/PROJECT_KNOWLEDGE.md` (stable public facts).
2. Read the latest entries in `knowledge/DECISIONS.md`.
3. Read this MEMORY.md (private local context).
4. Read the last 2 entries in SESSION_LOG.md.
5. Apply all rules before taking any action.

**End of session:**
1. Append one entry to SESSION_LOG.md (errors, fixes, prevention).
2. Update `knowledge/` files only for stable, sanitized, shareable facts.
3. Update MEMORY.md only for private/local context that should not be versioned publicly.
4. Never write secrets, real credentials, or local machine paths in any committed file.

## What Belongs Here vs knowledge/

| Here (.codex/) | In knowledge/ |
|---|---|
| Local machine paths | Stable tech facts |
| Debug session logs | Recurring gotchas |
| In-progress task state | Architectural decisions |
| Private env details | Public build defaults |

## Secret Prohibition

Real passwords, tokens, API keys, and credentials must NEVER appear in any `.codex/` file.
Use placeholders: `<WIFI_PASSWORD>`, `<API_KEY>`, `"present in local secrets.yaml (not versioned)"`.
