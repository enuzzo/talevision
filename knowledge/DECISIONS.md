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

## 2026-03-07 - Playlist / Rotation System

- Context: With 2 active modes (LitClock, SlowMovie) and 2 planned (Teletext, ANSi Art), users want to run multiple modes cycling automatically without manual switching.
- Decision: Orchestrator supports an ordered playlist of enabled modes. In rotation (2+ modes), a unified `rotation_interval` replaces per-mode intervals. Single mode uses per-mode interval as before. Persisted to `user_prefs.json`.
- Impact/Tradeoffs: Simple sequential round-robin — no complex scheduling. Unified interval avoids config explosion. Per-mode intervals still exist for single-mode operation. Drag-to-reorder in UI uses simple up/down arrows (no DnD dependency).

## 2026-03-07 - ScryBar Design System for Web Dashboard

- Context: Dashboard used a custom dark theme (DM Mono + Syne, amber accent, sharp edges). Netmilk Studio has a proper design system (ScryBar v1.4) used across projects.
- Decision: Retheme dashboard with ScryBar default: deep navy palette (#070D2D), violet accent (#7551FF), cyan secondary (#39B8FF), Montserrat + Space Mono, rounded corners (8px/12px/16px). Netmilk SVG logo in footer.
- Impact/Tradeoffs: Consistent brand identity across Netmilk products. Google Fonts dependency (Montserrat, Space Mono) — acceptable since dashboard requires internet for initial font load (cached after).

## 2026-03-07 - Suspend Screen Labels: "SUSPEND" not "ACTIVE"

- Context: Suspend screen showed "ACTIVE HOURS 23──07" which is confusing — 23→07 is the suspend window, not the active window.
- Decision: Labels changed to "SUSPEND HOURS" and "SUSPEND DAYS". Values are the raw config suspend window (start=sleep, end=wake). Dashboard still shows the UX-inverted "active hours" for intuitive editing.
- Impact/Tradeoffs: Suspend screen is now semantically correct. Two different presentations of the same data (suspend screen = raw, dashboard = inverted) — documented in PROJECT_KNOWLEDGE.md.

## 2026-02-28 - SHA256 File Hash as Video Cache Key (SlowMovie)

- Context: Video info (duration, fps, frame count) is slow to fetch via ffprobe. Need a stable, content-based cache key.
- Decision: SHA256 of the video file path used as the cache key in `VideoInfoCache`.
- Impact/Tradeoffs: Stable across renames as long as file content is unchanged. Slight overhead on first run; negligible thereafter.
