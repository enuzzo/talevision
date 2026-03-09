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

## 2026-03-07 - Suspend Day Semantics: Full-OFF Days + Time Window on Active Days

- Context: Original scheduler treated `days` as "days when the suspend time window applies". Days not in the list were never suspended — making it impossible to fully suspend weekends while keeping weekdays on a schedule.
- Decision: `days` now means "days the device is fully OFF (24h suspend)". Days NOT in the list are "active days" where the time window applies. UI shows "active days" (inverted at API boundary, same as hours). `next_wake_time()` skips past full-suspend days to find the first active day.
- Impact/Tradeoffs: Breaking semantic change in `days` field. Both hours AND days are now inverted at the UI boundary. Existing `config.yaml` `days: [0,1,2,3,4,5,6]` means "all days fully suspended" — empty list means "time window on all days". Users with saved `user_prefs.json` may need to re-save their schedule from the dashboard.

## 2026-03-07 - Suspend Screen Labels: "SUSPEND" not "ACTIVE"

- Context: Suspend screen showed "ACTIVE HOURS 23──07" which is confusing — 23→07 is the suspend window, not the active window.
- Decision: Labels changed to "SUSPEND HOURS" and "SUSPEND DAYS". Values are the raw config suspend window (start=sleep, end=wake). Dashboard still shows the UX-inverted "active hours" for intuitive editing.
- Impact/Tradeoffs: Suspend screen is now semantically correct. Two different presentations of the same data (suspend screen = raw, dashboard = inverted) — documented in PROJECT_KNOWLEDGE.md.

## 2026-03-08 - Manual Inky Driver Initialization (ac073tc1a)

- Context: `inky.auto.auto()` fails with "No EEPROM detected!" because the Inky Impression 7" board lacks an EEPROM chip for auto-detection. The older `inky.inky_uc8159` driver doesn't support 800×480.
- Decision: Use `from inky.inky_ac073tc1a import Inky` with explicit `resolution=(800, 480)`. Removed all `inky.auto` usage.
- Impact/Tradeoffs: Hardcoded to one display model. If the hardware changes, `canvas.py` must be updated. Acceptable since this is a single-device project.

## 2026-03-08 - Welcome Screen Boot Splash

- Context: After reboot, the e-ink display stays blank for ~30 s while TaleVision loads. No visual confirmation that the system is alive.
- Decision: Show a 15-second BBS/NFO-style welcome screen (white background, colourful header, system info box) before entering the main render loop. Systemd service set to `Restart=always` for reliable autostart.
- Impact/Tradeoffs: Adds ~45 s to first useful frame (15 s display + ~30 s e-ink refresh). Worth it for boot confidence. The 15 s timer is interruptible if needed.

## 2026-03-09 - Suspend Screen: White Background, Sleep Until next_wake_time

- Context: Suspend screen used black background (hard to read in daylight). Loop slept for `effective_interval` (300s) during suspend, causing periodic display refreshes. `set_suspend_schedule()` via API didn't wake a sleeping loop, so changes took effect only hours later.
- Decision: White background with orange header and rainbow border bars (matching welcome screen). Loop sleeps until `next_wake_time()` (actual resume datetime) instead of per-mode interval. `set_suspend_schedule()` resets `_suspended_displayed` and interrupts the timer.
- Impact/Tradeoffs: Display refreshes once on suspend entry and holds. API schedule changes apply immediately.

## 2026-03-09 - Thread Safety Audit: _lock Covers Playlist and Interval State

- Context: Code review identified that `set_playlist()` wrote to `_playlist`/`_playlist_index`/`_rotation_interval` without `_lock`, and `get_status()` read those fields also without `_lock`. Race with the main loop's playlist advance (under `_lock`) could cause IndexError or stale API responses.
- Decision: `set_playlist()` acquires `_lock` around all writes and derives `switch_needed` inside before releasing. `get_status()` acquires `_lock` to snapshot playlist/interval state before building the response.
- Impact/Tradeoffs: Correct thread safety at the cost of slightly more lock contention on `_lock`. Acceptable — `get_status()` is called at most every 2–12 s and holds the lock for microseconds.

## 2026-03-09 - Remove is_suspended from DisplayMode.render()

- Context: `render(is_suspended=True)` was dead code — the orchestrator handles suspend before calling `render()`, so modes never received `is_suspended=True`. Both `LitClockMode` and `SlowMovieMode` had unreachable branches that imported/built unused objects.
- Decision: Remove `is_suspended` parameter from `DisplayMode.render()` ABC and both implementations. Orchestrator calls `active.render()` unconditionally.
- Impact/Tradeoffs: Cleaner interface. New modes must not handle suspend logic in `render()` — the orchestrator owns that responsibility entirely.

## 2026-02-28 - SHA256 File Hash as Video Cache Key (SlowMovie)

- Context: Video info (duration, fps, frame count) is slow to fetch via ffprobe. Need a stable, content-based cache key.
- Decision: SHA256 of the video file path used as the cache key in `VideoInfoCache`.
- Impact/Tradeoffs: Stable across renames as long as file content is unchanged. Slight overhead on first run; negligible thereafter.
