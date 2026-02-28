# TaleVision — Claude Code Instructions

## Shared Knowledge

At session start, read:

- `knowledge/PROJECT_KNOWLEDGE.md` — stable technical context, stack, rendering invariants, gotchas.
- `knowledge/DECISIONS.md` (latest entries) — architectural decisions.

These files are the single source of truth for project-level facts.
Do not duplicate their content here.

## Behavioral Rules

- Never modify files in `archive/` — reference only, always gitignored.
- Never commit `secrets.yaml`, `media/*.mp4`, or any file containing real credentials.
- Before any push, verify the pre-push checklist in `knowledge/PROJECT_KNOWLEDGE.md`.
- Rendering invariants (LitClock typography, SlowMovie PIL chain, overlay) are non-negotiable — preserve exactly.
- Pi Zero W lean: no headless browsers, no heavy ML deps. PIL + Flask + inky only.
- Write all files in English. Conversation with the user is in Italian.
- Prefer editing existing files over creating new ones. Do not add comments or docstrings to code you didn't change.
