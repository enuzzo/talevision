# .codex — TaleVision Agent Memory System

This folder is shared between Claude Code and Codex CLI.

## Files
- **MEMORY.md** — Curated, stable rules. Short. Updated only when a rule is confirmed stable.
- **SESSION_LOG.md** — Append-only diary. One entry per session. Never delete entries.
- **README.md** — This file.

## Start-of-session ritual
1. Read MEMORY.md fully
2. Read the last 2 entries in SESSION_LOG.md
3. Apply all rules before taking any action

## End-of-session ritual
1. Append one entry to SESSION_LOG.md (errors, fixes, prevention)
2. Update MEMORY.md only if a new rule is stable and reusable
3. Never write secrets or real credentials anywhere in .codex/

## Secret prohibition
Real passwords, tokens, API keys, and credentials must NEVER appear in any .codex/ file.
Use placeholders: <WIFI_PASSWORD>, <API_KEY>, "present in local secrets.yaml (not versioned)".
