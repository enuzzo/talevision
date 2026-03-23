# TaleVision — Claude Code Instructions

## Deploy Model — EVERYTHING RUNS ON THE PI

TaleVision runs **entirely on the Raspberry Pi Zero W**, not on the Mac.
The Mac is ONLY for editing code, running unit tests, and `--render-only` smoke tests.

- **NEVER** launch dev servers locally (no `python3 main.py`, no `npm run dev`, no launch.json).
- **NEVER** propose running the backend or frontend on the Mac.
- The only legitimate local command is `python3 main.py --render-only --mode <name>` for rendering tests.
- Deploy workflow: **commit → push → SSH to Pi → `git pull` → `sudo systemctl restart talevision`**.
- Frontend build (`cd frontend && npm run build`) runs on the Mac, output is committed to repo, Pi serves it after `git pull`.

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
