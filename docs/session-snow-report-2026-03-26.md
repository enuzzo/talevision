# TaleVision v3.0 — Session Snow Report
**2026-03-26 · Deep audit by 5 parallel agents**

---

## Executive Summary

5 specialist agents reviewed the entire TaleVision codebase: security, backend quality, frontend quality, architecture, and visual UI/UX. The project is solid — **0 critical security issues**, well-structured modes, clean PIL rendering pipeline, and a cohesive design. The main areas for improvement are: code duplication across modes, some thread safety gaps, touch target sizes on mobile, and contrast fine-tuning.

**Overall design rating: 7.0/10** — excellent foundation, needs calibration on contrast/touch targets to reach 8.5+.

---

## 1. SECURITY

### High
| # | Finding | File | Fix |
|---|---------|------|-----|
| S1 | **No authentication on dashboard** — anyone on LAN has full control | `web/app.py` | Add optional API token or basic auth behind env var |

### Medium
| # | Finding | File | Fix |
|---|---------|------|-----|
| S2 | Hardcoded Flask `SECRET_KEY` | `web/app.py:26` | Use `os.urandom(32)` at startup |
| S3 | Gemini API key in URL query string (visible in logs) | `koan_generator.py:112-115` | Use `Authorization` header if API supports it |
| S4 | Weather fetched over HTTP not HTTPS (location in cleartext) | `weather.py:52` | Known Pi Zero W TLS issue; document clearly |

### Low
| # | Finding | File | Fix |
|---|---------|------|-----|
| S5 | Error responses leak exception strings to clients | `web/api.py` (multiple) | Return generic messages, log details server-side |
| S6 | Weather `lang` param not validated/encoded | `weather.py:52`, `api.py:203` | Whitelist valid language codes |
| S7 | No rate limiting on API endpoints | `web/api.py` | Add basic throttle on `/api/refresh` |
| S8 | No input validation on `set_language`, `set_interval` | `web/api.py` | Validate at API boundary, return 400 |

### Positive
- `yaml.safe_load()` used everywhere (no code execution risk)
- `secrets.yaml` properly gitignored
- No subprocess injection, no XSS, no path traversal
- No hardcoded secrets in tracked files

---

## 2. BACKEND CODE QUALITY

### Critical (design)
| # | Finding | File | Fix |
|---|---------|------|-----|
| B1 | **API layer accesses private `_` attributes** of orchestrator/modes (~15 occurrences) | `web/api.py` | Add public methods to Orchestrator |
| B2 | **Thread safety: `set_weather_units` bypasses orchestrator** — directly uses `_action_queue` | `api.py:246-247` | Add `set_weather_units()` public method |
| B3 | **KoanArchive ID generation races** — `len(files) + 1` is not atomic | `koan_archive.py:37-38` | Derive ID from timestamp filename |

### High (duplication & efficiency)
| # | Finding | Files | Fix |
|---|---------|-------|-----|
| B4 | **Fonts loaded independently per mode** — same TTF files loaded 3-5x | All 7 modes | Create shared `FontRegistry` singleton |
| B5 | **QR code generation duplicated** in 3 modes (SlowMovie, Museo, Cucina) | `slowmovie.py`, `museo.py`, `cucina.py` | Extract `render_qr_overlay()` utility |
| B6 | **`_load_font()` copy-pasted** in 5 files identically | 5 mode files | Move to `render/typography.py` |
| B7 | **`_wrap_text()` duplicated** in 3 files with variants | `wikipedia.py`, `cucina.py`, `suspend_screen.py` | Consolidate in `typography.py` |
| B8 | **Secrets loaded twice** — `main.py` + `KoanMode.__init__` each parse `secrets.yaml` | `main.py:87`, `koan.py:46` | Pass secrets via config/constructor |
| B9 | **Welcome/suspend screens share ~100 lines** of identical helper code | `welcome_screen.py`, `suspend_screen.py` | Extract `bbs_helpers.py` |

### Medium
| # | Finding | File | Fix |
|---|---------|------|-----|
| B10 | `_frame_paths` missing koan and cucina — `/api/frame/koan` returns 404 | `orchestrator.py:49-56` | Add entries for all 7 modes |
| B11 | `__init__.py` exports only 2 of 7 modes | `modes/__init__.py` | Update `__all__` |
| B12 | SHA256 hash reads entire video file for cache key | `frame_cache.py:24-36` | Use size+mtime instead |
| B13 | Weather ANSI render: 3500 individual `draw.text()` calls per render | `weather.py:226-254` | Batch consecutive same-color chars |
| B14 | Wikipedia loads fonts inside `render()` every cycle | `wikipedia.py:179-182` | Cache in `__init__` |
| B15 | Museo `_enhance()` runs even when values are 1.0 (identity) | `museo.py:149-153` | Guard with `if value != 1.0` |
| B16 | `AnsiConfig` in schema.py is dead code (mode banned) | `schema.py:128-131` | Remove |

---

## 3. FRONTEND CODE QUALITY

### High
| # | Finding | File | Fix |
|---|---------|------|-----|
| F1 | **Drag-and-drop has no keyboard or touch alternative** — playlist reorder is desktop-mouse-only | `App.tsx:381-408` | Add up/down arrow buttons as fallback |
| F2 | **Nearly zero `aria-` attributes** on custom interactive elements | Throughout `App.tsx` | Add `aria-label`, `role="checkbox"`, `aria-checked` |
| F3 | **Day buttons 'T'/'T' and 'S'/'S' indistinguishable** to screen readers | `App.tsx:659-673` | Add `aria-label="Tuesday"` etc. |
| F4 | **useEffect missing `input` dependency** in WeatherSettings | `App.tsx:1117` | Add `input` to deps array |

### Medium
| # | Finding | File | Fix |
|---|---------|------|-----|
| F5 | **No error feedback on 8 mutations** — failures are silent | All mutation hooks | Add `onError` handlers with user-visible toast/message |
| F6 | **Dead Google Fonts import** (Syne + DM Mono) in `index.html` | `index.html:7-12` | Remove `<link>` tags |
| F7 | **App.tsx at 1462 lines** — extract KoanArchivePage, WeatherSettings, PlaylistEditor | `App.tsx` | Split into 3-4 component files |
| F8 | **Koan archive uses raw `fetch()`** bypassing `api.ts` error handling | `App.tsx:858, 900` | Use `api.ts` helpers |
| F9 | **`ParticleBackground.tsx` is dead code** — 129 lines, never imported | `ParticleBackground.tsx` | Delete |

### Low
| # | Finding | File | Fix |
|---|---------|------|-----|
| F10 | Unused deps: `clsx` and `tailwind-merge` never imported | `package.json` | Remove |
| F11 | `useCallback(handleRefresh)` provides zero memoization benefit | `App.tsx:1293` | Remove `useCallback` wrapper |
| F12 | Inline `onFocus`/`onBlur` border style manipulation repeated 6x | `App.tsx` | Use CSS `:focus` rule instead |
| F13 | `KoanHaiku` type defined in App.tsx instead of `types.ts` | `App.tsx:843` | Move to `types.ts` |
| F14 | `NoiseCanvas` uses `setTimeout` instead of `requestAnimationFrame` | `App.tsx:153` | Switch to rAF (pauses in background tabs) |

---

## 4. ARCHITECTURE & DEPLOYMENT

### High
| # | Finding | File | Fix |
|---|---------|------|-----|
| A1 | **`install_service.sh` path wrong** — looks for `$PROJECT_DIR/talevision.service` but file is at `deploy/talevision.service` | `install_service.sh:8` | Fix path |

### Medium
| # | Finding | File | Fix |
|---|---------|------|-----|
| A2 | **`_interval_overrides` dict has no lock** — mutated from Flask thread, read from main loop | `orchestrator.py:164,169,189` | Add to `_lock` scope or funnel through queue |
| A3 | **Weather location set without lock** — `set_location()` from Flask, `render()` reads from main loop | `orchestrator.py:134-139` | Add lock in WeatherMode or route through queue |
| A4 | **No `MemoryMax` in systemd unit** — runaway process can OOM the Pi | `talevision.service` | Add `MemoryMax=400M` |
| A5 | **Config typos silently ignored** — `dacite strict=False` | `loader.py:38` | Log warning on unknown keys |
| A6 | **`install.sh` references user `pi`** but service runs as `enuzzo` | `install.sh:34` | Fix user reference |
| A7 | **Unbounded `resp.read()`** on museum/cucina image fetch — no size limit | `museo.py:141`, `cucina.py:151` | Add max size guard |
| A8 | **No HTTP connection reuse** — every API call opens a new TCP+TLS connection | All modes using `urllib.request` | Consider `requests.Session` |
| A9 | **`pyte` in requirements.txt is unused** — dead dependency | `requirements.txt:12` | Remove |
| A10 | **`.superpowers/` and test PNGs not in .gitignore** | `.gitignore` | Add patterns |

### Low
| # | Finding | File | Fix |
|---|---------|------|-----|
| A11 | Koan should fall back to cached haiku on API failure (currently shows error screen) | `koan.py` | Serve random archived haiku |
| A12 | No `WatchdogSec` in systemd — can't detect hung process | `talevision.service` | Add watchdog |
| A13 | Missing `Wants=network-online.target` — modes may fail on boot before network ready | `talevision.service` | Add dependency |
| A14 | Versions not pinned in requirements.txt (except waitress) | `requirements.txt` | Pin or add lockfile |

---

## 5. VISUAL UI/UX

### Design Strengths
1. **CRT rendering overlay** — genuinely delightful mode-switch animation with scanlines, noise, flicker, radio waves
2. **Three-font typography system** — Lobster/Funnel Display/Space Mono create clear hierarchy without clashing
3. **Information architecture** — logical top-to-bottom flow, conditional sections keep it clean

### Contrast Issues (WCAG)
| # | Element | Ratio | Required | Fix |
|---|---------|-------|----------|-----|
| V1 | **White text on `#FF1DA5` buttons** | ~3.6:1 | 4.5:1 (AA) | Use darker accent or dark text |
| V2 | **Dividers at `rgba(0,0,0,0.06)`** | Nearly invisible | Visible | Bump to `rgba(0,0,0,0.12)` |
| V3 | **Frame preview border at `rgba(0,0,0,0.08)`** | Very faint | Visible | Bump to `rgba(0,0,0,0.12)` |
| V4 | **Unchecked toggle** — cream on cream | Very low | Distinguishable | Darken track to `#E0DDD6` |
| V5 | **Focus ring at 12% opacity** | May be invisible for low-vision users | Visible | Bump to 25% |

### Touch Targets (Mobile)
| # | Element | Current | Minimum | Fix |
|---|---------|---------|---------|-----|
| V6 | Day-of-week chips | 36×36px | 44×44px | Increase to `w-11 h-11` |
| V7 | Playlist checkboxes | 20×20px | 44×44px | Make entire row the tap target |
| V8 | Grip drag handles | 8×12px | 44×44px | HTML5 drag doesn't work on mobile anyway |

### Other UI
| # | Finding | Fix |
|---|---------|-----|
| V9 | `max-w-2xl` (672px) feels narrow on desktop; jarring jump to `max-w-7xl` for Koan archive | Consider responsive container or smooth transition |
| V10 | Netmilk logo has `cursor-pointer` but no link destination | Add link or remove pointer |
| V11 | No initial loading skeleton — dashboard renders with fallback `'---'` values before first API response | Add subtle loading state |

---

## Priority Matrix

### Do First (quick wins, high impact)
1. **F6** — Remove dead Google Fonts import from `index.html` (1 line, saves network request)
2. **F9** — Delete `ParticleBackground.tsx` (dead code)
3. **F10** — Remove unused `clsx` and `tailwind-merge` from `package.json`
4. **A9** — Remove `pyte` from `requirements.txt`
5. **A10** — Add `.superpowers/` and `talevision_frame_*.png` to `.gitignore`
6. **B16** — Remove `AnsiConfig` from `schema.py`
7. **V2/V3** — Bump border opacity from 0.06/0.08 to 0.12 (CSS token change)

### Do Soon (moderate effort, important)
8. **B4** — Create shared `FontRegistry` (saves memory on Pi)
9. **B5/B6/B7** — Extract shared utilities (`render_qr_overlay`, `_load_font`, `_wrap_text`)
10. **B10** — Add koan/cucina to `orchestrator._frame_paths`
11. **F5** — Add `onError` handlers to mutations (user feedback)
12. **V1** — Fix button text contrast (darken accent or use dark text)
13. **V6** — Increase day chip touch targets
14. **A4** — Add `MemoryMax=400M` to systemd unit

### Do Later (larger scope)
15. **F1** — Add keyboard/touch alternative for playlist reorder
16. **F7** — Split App.tsx into component files
17. **B1** — Add public methods to Orchestrator, stop accessing `_` privates
18. **A2/A3** — Fix thread safety for interval overrides and weather location
19. **S1** — Add optional auth (API token or basic auth)
20. **A11** — Koan fallback to cached haiku on API failure

---

*Generated by 5 parallel Claude agents · ~800s total analysis time · 0 files modified*
