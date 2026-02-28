# Decisions

Concise ADR-style log for stable project decisions.

Entry format:

## YYYY-MM-DD - Title

- Context:
- Decision:
- Impact/Tradeoffs:

---

## 2026-02-28 - Introduce Public Cross-Assistant Knowledge Layer

- Context: Project had two private memory systems (.codex/ for Codex CLI, .claude/ for Claude Code). Neither was portable to other assistants or visible to human collaborators.
- Decision: Move stable, sanitized project knowledge to versioned `knowledge/`; keep private operational and debug logs in local non-versioned files (.codex/, .claude/memory/).
- Impact/Tradeoffs: Better portability and transparency across assistants. Stricter sanitization required — no local paths, IPs, or secrets in `knowledge/`.

## 2026-02-28 - Unified Display Architecture (One Pi, Two Modes)

- Context: LitClock and SlowMovie each ran on a separate Pi Zero W with separate Flask servers, same wall, same Inky Impression technology.
- Decision: Merge into a single Python package (TaleVision) with a mode-switching Orchestrator. One Pi, one config file, one Flask dashboard, shared Inky canvas.
- Impact/Tradeoffs: Halves hardware cost; cleaner architecture. Requires careful thread safety (main loop + Flask daemon thread via queue + lock). No new external dependencies beyond what both originals used.

## 2026-02-28 - E-Ink Refresh Intervals Deliberately Longer Than Panel Cycle

- Context: Inky Impression 7-colour takes ~30 s to refresh. Naive users may assume the display is frozen.
- Decision: LitClock at 60 s, SlowMovie at 90 s — both longer than the panel cycle. Documented in README. No workaround code added.
- Impact/Tradeoffs: Correct, intentional behaviour. Panel always finishes before next update. Users occasionally confused; README addresses this explicitly.

## 2026-02-28 - Vertical Centering Adjustment (LitClock)

- Context: Mathematical vertical centering on a wide panel (800×480) made quote text appear to sit low visually.
- Decision: Apply a configurable `vertical_centering_adjustment` upward offset (default 40 px) subtracted from the mathematical centre.
- Impact/Tradeoffs: Visually correct for typical quote lengths. Value is config-tunable. Must be preserved in any render refactor.

## 2026-02-28 - SHA256 File Hash as Video Cache Key (SlowMovie)

- Context: Video info (duration, fps, frame count) is slow to fetch via ffprobe. Need a stable, content-based cache key.
- Decision: SHA256 of the video file path used as the cache key in `VideoInfoCache`.
- Impact/Tradeoffs: Stable across renames as long as file content is unchanged. Slight overhead on first run; negligible thereafter.
