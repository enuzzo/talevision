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

## 2026-03-10 - Wikipedia and Weather as First-Class Active Modes

- Context: Wikipedia and Weather were planned/upcoming modes. Wikipedia was implemented; Weather was added to complete the "useful information on the wall" concept.
- Decision: Both promoted to first-class active modes in the playlist registry. Wikipedia fetches random articles via REST API (multi-language, PIL render, no headless browser). Weather uses wttr.in structured JSON (no API key), HTTP not HTTPS (HTTPS TLS handshake reliably times out on Pi Zero W armv6l).
- Impact/Tradeoffs: 4 active modes total. wttr.in HTTP constraint is Pi Zero W-specific — document clearly to avoid "why are you using HTTP?" questions.

## 2026-03-10 - Vintage Cream Palette Replacing ScryBar Design System

- Context: ScryBar v1.4 (deep navy + violet) was applied in March 2026 for brand consistency. After implementing it, the design felt too generic/corporate for a wall-mounted literary/cinematic device.
- Decision: Replace with a warm vintage cream palette: bg `#F1EBD9`, primary `#3B3C47`, accent `#CA796D` (Contessa rose). Tailwind config custom-extended. No ScryBar dependency.
- Impact/Tradeoffs: More characterful, fits the "literary device on the wall" context. No external design system dependency. New team members won't find a ScryBar reference and be confused.

## 2026-03-10 - Lobster as Logotype/Heading Typeface; Funnel Display as Interface Body

- Context: Dashboard had Sarina (Google Fonts decorative) as the logotype font. Sarina is too quirky without being warm.
- Decision: Lobster (Pablo Impallari, 2010) replaces Sarina for logotype and section headings (`font-title`). Funnel Display (Mirko Velimirović, 2024) replaces Montserrat/Space Mono for all interface text. OpenType ligatures and `optimizeLegibility` enabled for Lobster via CSS `font-feature-settings`.
- Impact/Tradeoffs: Lobster is widely recognised as a "classic web font" — risk of nostalgia overload. Works here because the project has enough personality to carry it. Funnel Display is contemporary and clean without being generic.

## 2026-03-10 - CRT Vintage RenderingOverlay (Replacing Cyberpunk/Sci-Fi Design)

- Context: Mode-switch overlay used neon scan line + rings + brackets (cyberpunk aesthetic). Felt modern and generic; inconsistent with the warm vintage palette.
- Decision: Replace with a CRT/radio-tuning aesthetic: dark warm `#19120C` background, animated TV grain via `NoiseCanvas` (tiny canvas scaled with `imageRendering: pixelated`), CSS CRT scanlines, amber sweep band, `TuningGauge` SVG (oscillating needle animating via Tailwind `gauge-needle` keyframe), mode name in Lobster with `animate-flicker`.
- Impact/Tradeoffs: SVG `transform-origin` on `<line>` elements doesn't work cross-browser. Workaround: wrap needle in `<g transform="translate(cx,cy)">`, apply `transform-box: fill-box; transform-origin: 50% 100%` to the `<line>` — rotates around the line's own bottom point.

## 2026-03-10 - TV Frame Background for Welcome and Suspend Screens

- Context: Welcome and suspend screens used rainbow colour bars for visual framing. The bars were thin (4–6px), and faint colours (green/yellow) were barely visible on the white e-ink background.
- Decision: Composite `assets/img/talevision-frame.png` (RGBA, 800×480, dark TV bezel with transparent centre) on white as the background for both screens. Remove rainbow bars entirely. Adjust minimum y-offset to 28px to keep content inside the frame's inner area.
- Impact/Tradeoffs: Consistent visual identity across boot and suspend. Frame is in git so it deploys with the code. E-ink renders the dark grey bezel as black (dithered) — looks correct. If frame PNG is missing, screens fall back gracefully to white background.

## 2026-03-10 - Welcome Screen: 30s Splash + Random Tagline + Screenshot Saved

- Context: 15-second welcome was too short to read on physical e-ink (panel refresh takes ~55s). Tagline was static. No way to inspect the welcome screen after boot without a camera.
- Decision: Extend to 30 seconds. Replace static tagline with `random.choice(TAGLINES)` from the same 20-item pool used in the web dashboard. Save rendered image to `cache/welcome_frame.png` via `_save_frame()` immediately after `canvas.show()`.
- Impact/Tradeoffs: Boot-to-first-content is now ~85s (30s welcome + 55s e-ink refresh). Acceptable for a wall display. Screenshot lets developers/operators inspect the welcome screen without physical access.

## 2026-03-10 - Wikipedia: Proportional Thumbnail + Full Extract + QR Zone Clipping

- Context: Thumbnail was force-cropped to 4:3, breaking articles with portrait images. Body text used only the short intro from the summary API. Text overflowed into the QR code area at the bottom-right.
- Decision: (1) Resize thumbnail to `THUMB_W=180px` maintaining original aspect ratio — no crop. (2) Make a second API call (`action=query&prop=extracts&exchars=3000`) to fetch full article text beyond the intro. (3) Per-line width calculation: beside thumbnail → `narrow_w`, in QR zone → `qr_safe_w`, otherwise → `full_w`. Last clipped line gets ` …`; QR message in Signika 16pt grey centred in the QR zone.
- Impact/Tradeoffs: Two HTTP calls per render (summary + extract) — both fast, Pi Zero W handles it within the 10s timeout. Text now fills the panel and visually respects the QR code.

## 2026-03-11 - Weather Mode: ANSI Terminal Rendering with Two-Zone Layout

- Context: Weather mode used wttr.in JSON (`?format=j1`) with a custom PIL layout (large temperature in Signika-Bold 80pt, custom forecast table). The result looked generic and didn't capture the charm of wttr.in's native terminal output with ASCII art weather icons.
- Decision: Rewrite Weather to fetch raw ANSI output from wttr.in, parse SGR escape codes char-by-char, map 16 ANSI colours to 7 e-ink colours (inverted: white bg, green→blue, yellow→orange), and render with Inconsolata Nerd Font Mono (125/125 Unicode glyph coverage verified). Two-zone layout: custom header ("City · HH:MM" in Signika-Bold 16pt) + current conditions at 14pt + forecast tables at 12pt. Location stored as city + lat/lon coordinates; autocomplete via Open-Meteo free geocoding API (replacing Nominatim). Metric/Imperial toggle.
- Impact/Tradeoffs: More visually distinctive — ASCII art icons + monospace terminal aesthetic on e-ink. Depends on wttr.in ANSI format stability. 6 Inconsolata font files added to assets. Open-Meteo geocoding is free with no key (Nominatim had rate limits).

## 2026-03-11 - SlowMovie: Re-pick Video on Each Playlist Rotation

- Context: SlowMovie selected a random video on first render and kept it forever in-memory (`_current_video`). In a 4-mode playlist, the same film replayed every rotation cycle indefinitely.
- Decision: Reset `_current_video = None` in `on_activate()`, so each time the playlist rotates back to SlowMovie, a new random video is picked.
- Impact/Tradeoffs: Truly random film experience in rotation. Within a single activation, the video is still sticky (consistent frames from the same film). Could theoretically pick the same film twice in a row by chance — acceptable with small media libraries.

## 2026-03-11 - Wikipedia: Remove QR Hint Text

- Context: Wikipedia mode showed a locale-specific "scan the QR to read more" message (`QR_MORE_MSG` dict, 6 languages) in the QR zone. The ellipsis and QR code are self-explanatory; the text was redundant.
- Decision: Remove `QR_MORE_MSG` dictionary, `font_qr_msg` font loading, and the QR message rendering block entirely.
- Impact/Tradeoffs: Cleaner layout, more space for article text. QR code is universally understood without instruction.

## 2026-03-11 - Welcome Screen Refinements

- Context: Welcome screen had `[ S T A R T I N G  I N  3 0  S E C O N D S ]` with letter-spacing and square brackets. Hostname showed bare name without `.local` mDNS suffix.
- Decision: Simplify to `— STARTING IN 30 SECONDS —` (em dashes, no letter-spacing). Append `.local` to hostname for mDNS discoverability.
- Impact/Tradeoffs: Cleaner typography. Hostname is now directly usable as a network address.

## 2026-03-13 - SlowMovie: Random Video Per Render + Reduced Skip Margins

- Context: SlowMovie picked a random video only once per `on_activate()` call. In single-mode operation (no playlist rotation), the same film played indefinitely — always "sticky" across render cycles. Additionally, `skip_start_seconds=120` and `skip_end_seconds=240` were too aggressive for short films (< 6 min), causing the valid frame range to collapse and fall back to full range (including credits/slates).
- Decision: When `video_file=random`, `_select_video()` now re-picks a random video on every render cycle (not just on activation). When a specific filename is configured, the selection remains sticky. Skip margins reduced to `skip_start_seconds=30`, `skip_end_seconds=120` — still avoids cold-open slates and end credits but works for short films too.
- Impact/Tradeoffs: Every 5-minute render shows a different film — more variety, but no continuity within a single film. Acceptable for e-ink "slow cinema" where each frame is a standalone photograph. Users wanting to watch one film can set `video_file` to a specific filename.

## 2026-03-13 - generate_sidecars.py: --verify Mode

- Context: After bulk-copying new films to `media/`, there was no quick way to verify all sidecar `.json` files existed and had valid content (title, year, director fields).
- Decision: Add `--verify` flag to `generate_sidecars.py`. Scans all videos, checks each has a `.json` with required fields, reports OK/MISSING/INVALID in a rich table. Exit code 0 if all valid, 1 if problems found.
- Impact/Tradeoffs: Dev-side verification tool only (not run on Pi in production). Uses `rich` for formatted output.

## 2026-03-23 - Museo Mode: Multi-Provider Public-Domain Artworks

- Context: TaleVision had 4 modes (LitClock, SlowMovie, Wikipedia, Weather). A visual art mode was the natural next step — museum APIs offer hundreds of thousands of public-domain artworks with no API key.
- Decision: Implement Museo mode with 3 providers (Metropolitan Museum of Art, Art Institute of Chicago, Cleveland Museum of Art) in deterministic round-robin rotation. File-based catalogue cache with 24h TTL. 50-ID recent buffer prevents repeats. Overlay matches SlowMovie's RGBA pattern (rounded-rect, alpha composite). Fallback to last cached frame on network failure.
- Impact/Tradeoffs: 3 HTTP calls per render (catalogue check + artwork detail + image fetch). AIC catalogue fetch can be slow on first cold cache (up to 100 pages). Round-robin is per-render, not per-session — provider index resets on restart. No API keys to manage. All three museums offer CC0/public-domain images.

## 2026-03-25 - Cucina Mode: World Recipes with Dark/Light Split Layout

- Context: TaleVision had 6 modes. A food/recipe mode was suggested from the roadmap (docs/ideas). TheMealDB offers a free API with no key required.
- Decision: Implement Cucina mode — random world dishes with full recipe details. Dark/light split layout: top half dark bg (35,30,25) with food photo (240×240 1:1 cover crop, 14px rounded corners), Lobster title in white (smart title case), ingredients in 1-2 columns. Bottom half white with instructions in Taviraj Regular 19pt. Dark footer bar with timestamp. QR links to YouTube tutorial or recipe source.
- Impact/Tradeoffs: Single HTTP call per render (fast). TheMealDB has ~300 recipes — less variety than Museo's ~973k artworks but sufficient for a wall display. Some meals have sparse data (missing tags, short instructions). Smart title case handles English prepositions but not all languages.

## 2026-03-25 - Koan: Synchronous Generation + 210 Surreal Themes + Multi-Language

- Context: With cloud LLM (~1s per haiku), the background generator and random replay architecture was over-engineered. Themes were limited to 20 contemplative words. Haiku were English-only.
- Decision: (1) Synchronous generation: every `render()` generates a fresh haiku directly, no background thread. Archive is purely historical (for dashboard browsing). Poetic error screen on API failure. (2) Expand seed themes from 20 to 210 — wild mix of surreal ("the autobiography of a pothole"), trivial ("stepping on dog poop at dawn"), and absurd ("a parking ticket on a hearse"). Themes stay in English in the header; haiku is written in the configured language for maximum contrast. (3) Multi-language support via `set_language()` from dashboard (same as LitClock/Wikipedia). Default `it`. System prompt adapts per language; the 70B model handles translation implicitly. **Note**: themes later pruned to 190 — see 2026-03-29 decision.
- Impact/Tradeoffs: Simpler architecture (no threading). Each render requires a working API call — no graceful degradation to cached haiku. Error screen is intentionally poetic. The English theme + local language haiku contrast is a deliberate aesthetic choice.

## 2026-03-25 - Koan Archive Wall Page

- Context: Haiku archive was a collapsible list in the dashboard, showing max 20 items. As haiku accumulate (96/day), this becomes unwieldy and the poems deserve better presentation.
- Decision: Dedicated full-page archive view with CSS columns masonry grid. Parchment-toned cards on dark gallery background (#0F0C08). Georgia serif italic for haiku text, gold theme headers, terracotta pen names. Search by theme/pen name/words. Load-more pagination (30/batch). Export ZIP button. Accessible via "view all →" link from dashboard panel.
- Impact/Tradeoffs: No React Router added — implemented as view toggle (useState). Single App.tsx remains the only component file. Export ZIP endpoint needs backend implementation.

## 2026-03-25 - Dashboard UX: Auto-Save Language + Inline Save Schedule

- Context: Multiple save buttons (playlist, language, schedule) created confusion — users didn't know what each button saved. Save Schedule button wasted a full row of vertical space.
- Decision: Language auto-saves on click (no button). Playlist keeps explicit "Save playlist" button. Schedule "Save" button moved inline after the weekday chips. Clear visual separation of what auto-saves vs explicit-saves.
- Impact/Tradeoffs: Reduces vertical space. Language change is instant (no "did it save?" confusion). Playlist still needs explicit save because reorder + interval are multi-step operations.

## 2026-03-25 - LitClock: Truncate Long Titles with Ellipsis

- Context: Some LitClock quotes have very long book titles that overflow the details line (author + separator + title), pushing text outside the 800px canvas width.
- Decision: Measure the full details line width. If it exceeds available width, truncate the title with "…" until it fits. Author name is never truncated (it's the more important attribution).
- Impact/Tradeoffs: Simple pixel-based truncation. Works for all languages and font sizes. The ellipsis hints that more information exists.

## 2026-03-25 - Koan: Cloud LLM Replacing Embedded LLM

- Context: Embedded LLM (SmolLM-135M via llama.zero on Pi Zero W) was too slow — ARM1176 at 1GHz produced ~0.05 tok/s effective, with 54MB of model weights swapped to SD. Each haiku attempt timed out at 1 hour without completing. Continuous swap I/O also risked SD card wear on a 24/7 device.
- Decision: Replace embedded LLM with cloud API: Groq (primary, `llama-3.3-70b-versatile`) + Google Gemini (fallback, `gemini-2.0-flash-lite`). Auto-detect from `secrets.yaml`. Generation drops from >1h (never completing) to ~1s. Dual backend: if Groq key exists use it, else try Gemini. Full metadata tracking: model, tokens, timing per haiku. Folder-based archive (one JSON per haiku).
- Impact/Tradeoffs: Requires internet + free API key (Groq: 100K TPD free, ~18K used at 96 haiku/day = 18%). Loses the "fully offline $5 poet" narrative but gains actual working poetry from a 70B model.

## 2026-03-24 - Koan Mode: Visual Design and Concept

- Context: TaleVision had 5 modes covering time, cinema, knowledge, weather, and art. A contemplative/generative mode was the natural complement — something the machine creates rather than fetches.
- Decision: Implement Koan mode — haiku where an LLM reflects on unexpected themes. Zen minimalist visual layout: bamboo ink wash bg, Crimson Text 46pt right-aligned haiku, Inconsolata Mono Bold for metadata (theme · № id header, pen name, tech stats).
- Impact/Tradeoffs: Crimson Text chosen over Fraunces (variable font axis issues with PIL default weight).

## 2026-03-24 - Museo: Replace AIC with V&A (3 Free Providers, No Keys)

- Context: AIC's IIIF image server behind Cloudflare JS challenge (403 for all non-browser requests). Needed replacement providers. Design principle: zero cost, zero registration — no API keys whatsoever.
- Decision: Remove AIC and Smithsonian (required free registration). Add Victoria and Albert Museum (no key, IIIF via framemark.vam.ac.uk, ~732k objects — largest single provider). Final roster: Met (~200k, no key), Cleveland (~41k, no key), V&A (~732k, no key). Total: ~973k public-domain artworks. Static `PROVIDERS` list, no factory function needed.
- Impact/Tradeoffs: Three providers, zero configuration, zero API keys. V&A alone is larger than AIC + Smithsonian combined. Can re-enable AIC if they lift Cloudflare challenge. AIC provider code kept in `aic.py` for future use.

## 2026-03-23 - Solar Dust Theme Replacing Vintage Cream Palette

- Context: The warm vintage cream palette (bg `#F1EBD9`, accent `#CA796D`) with Funnel Display font felt pleasant but lacked the "desert tech" character of the Vibemilk design system's Solar Dust theme.
- Decision: Full migration to Solar Dust: dark brown-black bg `#1A1410`, gold accent `#E8A838`, terracotta secondary `#D06B50`, cream text `#F0E6D6`. Display font changed to Chakra Petch (self-hosted woff2). Tailwind semantic token names kept identical — only values changed. All hardcoded ScryBar/cream hex values in App.tsx replaced systematically.
- Impact/Tradeoffs: Dark theme is more dramatic on mobile dashboard. Gold accent on dark bg has excellent contrast. Netmilk logo SVG no longer needs CSS `invert`. Mode accent colours re-tuned to Solar Dust harmonics (LitClock `#6A9FBF`, SlowMovie `#E8A838`, Wikipedia `#D06B50`, Weather `#7FA87F`, Museo `#B8860B`).

## 2026-03-25 - Vibemilk Default Theme Replacing Solar Dust

- Context: Solar Dust (dark brown-black bg, gold accent, Chakra Petch) was dramatic but too heavy for a literary/cinematic wall device dashboard. The Vibemilk design system's default light theme is warmer and more professional.
- Decision: Full migration to Vibemilk Default: warm milk-white bg `#F0EDE8`, magenta accent `#FF1DA5`, blue secondary `#5D84DF`, navy text `#1A1A2E`. Body font changed from Chakra Petch to Funnel Display (variable, self-hosted woff2). Lobster title and Space Mono mono kept. Mode colours vibrant for light bg (LitClock `#2563EB`, SlowMovie `#D97706`, Wikipedia `#DC2626`, Weather `#059669`, Museo `#7C3AED`, Koan `#4F46E5`, Cucina `#EA580C`). Koan archive page stays dark (`#121225`) as a gallery context. Rendering overlay stays dark with magenta scan tones. All ~50 hardcoded Solar Dust hex values in App.tsx replaced. Borders changed from gold-alpha `rgba(232,168,56,x)` to neutral `rgba(0,0,0,x)`.
- Impact/Tradeoffs: Light theme is easier to read in daylight. Magenta accent is distinctive and high-contrast. Button text changed from `text-bg` to `text-white` for WCAG AA compliance on magenta. Netmilk SVG logo works without filter on light bg (opacity-40).

## 2026-03-10 - Language Order: it / es / pt / en / fr / de

- Context: Languages were listed alphabetically (de/en/es/fr/it/pt) in default config and UI. Project context is Italian-first (deployed in Italy, Netmilk is Italian).
- Decision: Preferred order `["it", "es", "pt", "en", "fr", "de"]` — Italian first (home language), then Iberian peninsula, then English, then French/German. Applied in: `loader._LANG_ORDER`, `wikipedia.LANGS`, `schema.WikipediaConfig.languages` default.
- Impact/Tradeoffs: Trivial preference with zero technical cost. Makes language selector more intuitive for the primary user base.

## 2026-03-27 - Flora Mode: Generative Botanical Art via L-Systems

- Context: TaleVision had 7 display modes. All fetched external data (LitClock quotes, SlowMovie frames, Wikipedia articles, weather, museum artworks, recipes, AI haiku). A fully offline, purely algorithmic mode was missing — something that demonstrates the device can be interesting with zero network access.
- Decision: Add Flora mode — deterministic L-system botanical illustrations seeded by date. Eight botanical species (fern, tree, bush, vine, flower, bamboo, reed, spring bulbs) with production rules, depth-based line coloring (3 green shades), and species-specific terminal flowers (red, orange, yellow, pink, blue). Fake Latin names generated combinatorially. Layout: 500px plant panel (white) + 300px specimen label card (cream). Refresh 3600s — one new plant per day, same plant all day.
- Impact/Tradeoffs: Zero API calls, zero tokens, 100% offline. Render time ~1s on Pi Zero W. L-system strings capped at 80K chars to prevent runaway growth. The deterministic seed means the same date always produces the same botanical illustration, creating a calendar-like collectible quality.

## 2026-03-27 - Flora Archive: Daily Specimen Archive with Image Grid

- Context: Koan mode saves each generated haiku to a folder-based archive (JSON per entry, web page for browsing). Flora mode generates a unique botanical illustration each day — archiving them creates an ever-growing herbarium that grows richer over time.
- Decision: Flora saves both JSON metadata (species, genus, epithet, family, date, location) and a full 800×480 PNG to `cache/flora_archive/YYYYMMDD.{json,png}` on each render, idempotent within the same day. Two API endpoints: `GET /api/flora/archive` (metadata list, newest first) and `GET /api/flora/archive/<YYYY-MM-DD>` (serve PNG). Frontend: FloraArchivePage (light Vibemilk theme, responsive image grid, click-to-enlarge lightbox) + FloraArchivePanel (compact preview in dashboard sidebar). Unlike the Koan archive which stays dark, the Flora archive uses the light Vibemilk theme matching the illustrations' white/cream background.
- Impact/Tradeoffs: Each daily PNG is ~200-400KB; after one year ~100-150MB. Fine for Pi SD card. The archive grows automatically without any manual intervention.

## 2026-03-29 - Flora Rendering v2: Brown Trunk, Leaf Clusters, Bold Flowers

- Context: First Flora rendering produced bare stick-figure trees with no leaves, invisible flowers (prob too low), and a monochrome green palette with no trunk distinction.
- Decision: Rewrite `_turtle_draw` with depth-aware coloring (brown trunk `#482A12` at depth 0-1, graduating to green at tips), `_draw_leaf()` at every branch tip (3-ellipse cluster), `_draw_flower()` with 4 petals + yellow centre, ±2.5° angle jitter, line width 5→1 with depth. Flower probabilities raised significantly (bush 0.45, flower 0.60, vine 0.30, spring 0.45). Tree/bush/vine species use brown trunk; grass-like species (fern/bamboo/reed) remain all-green.
- Impact/Tradeoffs: Visually dramatic improvement — botanical illustrations now look like actual flowering plants. Render time still ~1s on Pi Zero W. Jitter is seeded from the same date-based RNG so remains fully deterministic.

## 2026-03-29 - Orchestrator frame_paths: Add koan/cucina/flora

- Context: The orchestrator had a hardcoded `_frame_paths` dict mapping mode names to PNG cache files. Koan, Cucina, and Flora were missing. Their frames were never saved to disk, causing the dashboard frame preview endpoint (`GET /api/frame`) to return 404 ("no signal") when any of these modes was active.
- Decision: Add `"koan"`, `"cucina"`, `"flora"` to `_frame_paths` in orchestrator `__init__`. Each mode's render loop already called `_save_frame(frame, active_name)` — it just silently skipped unknown names. The fix is a 3-line addition.
- Impact/Tradeoffs: All 8 modes now have working frame previews in the dashboard. Future modes must be added to `_frame_paths` at registration time.

## 2026-03-29 - Koan: Haiku/Koan Alternation + Surreal Themes Only

- Context: Koan mode only produced haiku. Philosophical themes ("consciousness", "existence", "silence") felt generic and boring on the wall. Curated fallback haiku were a leftover from the abandoned embedded LLM (llama.zero).
- Decision: (1) Strict alternation between haiku (3 lines + pen name) and paradoxical koan questions (single Zen riddle, no pen name). Based on `archive.count() % 2`. Fallback to haiku if koan generation fails. (2) Remove all 20 generic philosophical themes, keeping 190 exclusively surreal/creative ones. (3) Remove curated fallback haiku — either the LLM generates or the error screen shows. (4) Tech stats line prefixed with `HAIKU ·` or `KOAN ·`. (5) Archive JSON gains `"type"` field; API supports `?type=all|haiku|koan` filter. (6) Frontend: filter toggle in archive page, koan cards show no pen name.
- Impact/Tradeoffs: More variety on the wall. Koan questions use a different system prompt ("Zen master" vs "contemplative poet") and `max_tokens=100` (vs 60 for haiku). The alternation is deterministic from the archive count — visible in the tech stats line.

## 2026-03-29 - Flora: Time-Based Seed for Variety

- Context: Flora used `date.today().isoformat()` as seed, producing the same plant all day regardless of refresh interval. This was intended as a "one specimen per day" herbarium concept but felt boring.
- Decision: Changed seed to `datetime.now().isoformat()` — each render produces a unique plant. Archive still saves one per day (first render wins).
- Impact/Tradeoffs: Every refresh shows a different species/genus/form. Lost the "daily collectible" concept but gained actual visual variety.

## 2026-03-31 - APOD Mode: Sidebar Layout with Pure Black Panel

- Context: NASA APOD images vary widely in composition — some are landscape-dominated, others portrait, some abstract. A full-bleed layout loses the metadata context entirely. SlowMovie's bottom-band overlay pattern was considered but the variable text volume (explanation excerpts can be long) needed more real estate.
- Decision: Sidebar layout — image fills 500px of the left panel (`ImageOps.fit`, cover-cropped), metadata in a 300px pure-black panel on the right. Panel content top-to-bottom: `APOD · date` on one line (Inconsolata 20pt + 17pt), title in Lobster 26pt (max 3 lines), explanation body (Taviraj Italic 16pt, fills available space), horizontal divider, copyright (Inconsolata 14pt), clock footer (Inconsolata 17pt). Background: `(0,0,0)` — not 90% black, not a gradient, not dithered. Pure black. Random historical date (1995-06-16 to yesterday) seeded per refresh interval for deterministic variety.
- Impact/Tradeoffs: Panel text area is 268px usable width (300 - 32px margins). Lobster 26pt at that width wraps well for typical APOD titles (3-8 words). Sidebar occupies 37.5% of the screen but the image still dominates. The DEMO_KEY fallback (30 req/h) is sufficient for the cached-by-date fetch pattern — network call happens once per unique date, not once per render.

## 2026-03-31 - Mars Mode: Migration from deprecated NASA API to JPL Direct API

- Context: `api.nasa.gov/mars-photos` returned 404 "No such app" — the Heroku free tier shutdown took out this endpoint permanently. The mode was showing a "signal lost" error screen. Additionally, the previous implementation used `per_page=100`, which only returned the latest sol's photos — typically MAHLI (macro) and nav cameras, never the scenic Mastcam colour images.
- Decision: Migrate to `mars.nasa.gov/api/v1/raw_image_items/?order=sol+desc&per_page=500`. JPL direct API, no API key required, actively maintained. `per_page=500` is necessary to capture Mastcam photos from recent sols (e.g., sol 4850 has ~74 MAST_RIGHT photos spread across 500 results). Dropped Perseverance alternation — the JPL `?mission=mars2020` filter is silently ignored by the API; it always returns Curiosity data. Overlay rewritten for JPL field names (`instrument`, `title`, `date_received`, `date_taken`, `id`). `_camera_full_name()` strips the `"Sol N: "` prefix from the JPL `title` field. `_fmt_date()` extended to handle ISO datetime strings (`"2026-03-31T23:00:15.000Z"`). Overlay band made fully opaque `(0,0,0,255)` — no translucency for clean e-ink rendering. Clock line added as 4th overlay row.
- Impact/Tradeoffs: API is unauthenticated and public — no secrets to manage, no rate limits. `per_page=500` is a larger payload (~200KB JSON) but cached daily. The Curiosity-only limitation is an API constraint, not a design choice. Perseverance support can be re-enabled if JPL ever fixes the mission filter.
