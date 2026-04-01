# WebUI UX Redesign — Design Spec

**Date:** 2026-04-01
**Status:** Approved
**Scope:** Dashboard layout, save UX, mobile experience, visual polish

---

## 1. Goals

- Make the dashboard comfortable, space-efficient, and visually polished on both mobile and desktop
- Eliminate save confusion with a single global Save
- Provide a fixed action bar on mobile so Save and Force Refresh are always reachable
- Organize settings into clear, scannable card-based sections
- Reduce visual noise in interval controls

## 2. Non-Goals

- No new features or modes
- No changes to archive page content/logic (only responsive grid fix)
- No backend API changes (all existing endpoints are sufficient)
- No routing library — keep useState-based view switching

---

## 3. Layout

### 3.1 Desktop (lg+, >= 1024px)

**Max-width:** 1200px (down from 1440px) for tighter, more balanced proportions.

**Sticky header:** Logo + clock + status indicator + Save button + Force Refresh button. Save and Force Refresh live in the header on desktop — always visible without a bottom bar.

**Top row — 2 columns:**
- Left (~60%): Frame preview (aspect 5:3, `object-contain`) + status bar below (uptime, last render, wake time, rotation sequence)
- Right (~40%): Playlist editor (mode toggles with drag-and-drop, rotation interval input)

**Below — settings cards grid (2 columns):**
- Left column: Schedule card, then Weather + Language card (combined)
- Right column: Refresh Intervals card
- Full-width row: Archives card

**Footer:** Compact single line.

```
┌──────────────────────────────────────────────────────────┐
│ TaleVision        clock    ● mode    [Save] [↻ Refresh]  │
├──────────────────────────────────┬───────────────────────┤
│ Frame Preview (~60%)             │ Playlist (~40%)       │
│                                  │  ☐ LitClock           │
│ ┌─ status ─────────────────────┐ │  ☑ SlowMovie          │
│ │ UP 2h · LAST 14:32 · WAKE…  │ │  ☑ Wikipedia          │
│ └──────────────────────────────┘ │  ...                  │
│                                  │  Rotation: [5] min    │
├──────────────────────────────────┴───────────────────────┤
│ ┌─ Schedule ──────────────┐ ┌─ Refresh Intervals ──────┐ │
│ │ [On/Off toggle]         │ │ 🕐 litclock    [5] min   │ │
│ │ On from [09:00] → Off…  │ │ 🎬 slowmovie   [5] min   │ │
│ │ [M][T][W][T][F][S][S]   │ │ 📖 wikipedia   [5] min   │ │
│ └─────────────────────────┘ │ 🌤 weather     [5] min   │ │
│ ┌─ Weather + Language ────┐ │ ...                      │ │
│ │ Location [____] °C/°F   │ └──────────────────────────┘ │
│ │ Language [Italiano ▾]   │                              │
│ └─────────────────────────┘                              │
│ ┌─ Archives ───────────────────────────────────────────┐ │
│ │ [禅 Koan 142] [🌿 Flora 38] [🐑 Sheep 24]           │ │
│ └──────────────────────────────────────────────────────┘ │
│ TaleVision · Pi Zero W · 800×480 · github ↗             │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Mobile (< 1024px)

Single column, all sections stacked vertically. Fixed bottom action bar.

**Order (top to bottom):**
1. Sticky header (logo + status, compact)
2. Frame preview + status bar
3. Playlist card
4. Schedule card
5. Refresh Intervals card
6. Weather + Language card
7. Archives card
8. Footer
9. (60px spacer for bottom bar clearance)

**Fixed bottom bar:** 56px height, backdrop-blur, contains:
- Save button (left, primary)
- Force Refresh button (right, secondary/outline)

```
┌─────────────────────────┐
│ TaleVision    ● litclock│
├─────────────────────────┤
│ [Frame Preview]         │
│ UP 2h · LAST 14:32      │
├─────────────────────────┤
│ ┌─ Playlist ──────────┐ │
│ │ ...                 │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│ ┌─ Schedule ──────────┐ │
│ │ ...                 │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│ ┌─ Intervals ─────────┐ │
│ │ ...                 │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│ ┌─ Weather + Lang ────┐ │
│ │ ...                 │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│ ┌─ Archives ──────────┐ │
│ │ [禅] [🌿] [🐑]      │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│ footer                  │
│ (spacer 60px)           │
╞═════════════════════════╡
│ [● Save]    [↻ Refresh] │  ← fixed bottom
└─────────────────────────┘
```

---

## 4. Global Save UX

### 4.1 Dirty State Tracking

A `dirtyFields` set tracks which sections have unsaved changes. Populated by comparing local form state to the last-synced server values. Sections tracked:

- `playlist` — mode order, enabled set, or rotation interval changed
- `schedule` — enabled, times, or days changed
- `intervals` — any mode's interval value changed
- `weather` — location or units changed
- `language` — language changed

### 4.2 Save Button States

| State | Desktop (header) | Mobile (bottom bar) |
|-------|-----------------|-------------------|
| **Clean** | Ghost/dimmed button, text "Saved" | Ghost button, text "Saved" |
| **Dirty** | Filled magenta, text "Save changes" | Filled magenta, text "Save" |
| **Saving** | Spinner, disabled, "Saving..." | Spinner, disabled |
| **Just saved** | Green "✓ Saved" for 3s, then ghost | Green "✓ Saved" for 3s |
| **Error** | Red "Save failed" shake animation | Red "Failed" for 3s |

### 4.3 Save Behavior

On click, fires all pending mutations in parallel:
- If `playlist` dirty → `api.setPlaylist(modes, interval)`
- If `schedule` dirty → `api.suspend(config)`
- If `intervals` dirty → `api.setInterval(mode, seconds)` for each changed mode
- If `weather` dirty → `api.setWeatherLocation(...)` and/or `api.setWeatherUnits(...)`
- If `language` dirty → `api.setLanguage(lang)`

All mutations fire via `Promise.allSettled()`. Success → mark clean, show confirmation. Partial failure → show which section failed.

### 4.4 Force Refresh Button

Always enabled (not dependent on dirty state). Triggers `api.refresh()` and enters the existing render-waiting state with the overlay animation.

---

## 5. Component Changes

### 5.1 Remove Per-Section Save Buttons

- **PlaylistEditor**: remove the sticky Save bar and Force Refresh button from the component. These move to the global action bar/header.
- **SuspendForm**: remove the Save button and saved state.
- **IntervalRow**: remove the "Set" button. Keep only input + optional reset icon.
- **WeatherSettings**: remove the "Set location" button and saved state.

### 5.2 Lift State Up

All form state currently local to components must be accessible to the global Save handler. Approach: lift state to App component via props/callbacks, or use a lightweight context.

Recommended: pass `onChange` callbacks from App into each section component. App maintains the canonical dirty state and handles all saves.

### 5.3 New Components

**`ActionBar`** — the fixed bottom bar on mobile.
- Props: `dirty: boolean`, `saving: boolean`, `saved: boolean`, `error: boolean`
- Props: `onSave: () => void`, `onRefresh: () => void`, `refreshing: boolean`

**`SettingsCard`** — generic card wrapper for settings sections.
- Props: `title: string`, `children: ReactNode`
- Renders: rounded card with header, consistent padding, border, shadow.

### 5.4 Simplified IntervalRow

Current:
```
[icon] [name 80px] [input] min [Set btn] [reset?] [value display]
```

New:
```
[icon] [name] .............. [input] min [×reset if overridden]
```

- No "Set" button
- No right-aligned value display (the input IS the value)
- Subtle alternating row backgrounds for scannability
- "×" reset icon only visible when value differs from default

### 5.5 Weather + Language Combined Card

Single card titled "Preferences" or "Settings":
- Top: Weather location input + units toggle
- Divider
- Bottom: Language dropdown

This avoids a tiny standalone Language card.

---

## 6. Card Visual Design

All settings sections wrapped in a consistent card:

```css
background: #FFFAF0;
border: 1px solid rgba(0,0,0,0.08);
border-radius: 12px;
padding: 16px 20px;
box-shadow: 0 1px 3px rgba(0,0,0,0.04);
```

Card header: section title using existing `.label` class style (11px uppercase, tracking, 600 weight) in the card's top-left.

---

## 7. Archive Pages — Responsive Grid Fix

Current: `grid-cols-3` hardcoded on all archive pages.

New responsive grid:
```
grid-cols-1 sm:grid-cols-2 lg:grid-cols-3
```

Applied to: KoanArchivePage, FloraArchivePage, ElectricSheepArchivePage.

No other changes to archive page content or behavior.

---

## 8. Removed Elements

- **Tagline**: removed from dashboard (decorative, wastes space)
- **Per-section Save buttons**: all removed in favor of global Save
- **Per-interval "Set" buttons**: removed
- **Standalone Language section**: merged into Weather+Language card

---

## 9. Header Redesign

Current header: logo left, clock + status right.

New header (desktop):
```
[● TaleVision]    [clock]  [● mode]    [Save btn] [↻ Refresh btn]
```

New header (mobile):
```
[● TaleVision]    [● mode]
```
(clock can move to status bar below frame, or stay in header if space allows)

Action buttons are in the header on desktop, in the fixed bottom bar on mobile.

---

## 10. Responsive Breakpoints

| Breakpoint | Layout |
|-----------|--------|
| < 640px (mobile) | 1 column, fixed bottom bar, compact cards |
| 640-1023px (tablet) | 1 column, slightly wider cards, fixed bottom bar |
| >= 1024px (lg/desktop) | 2-column top + 2-column settings grid, header actions |

Max-width container: **1200px** (down from 1440px).

---

## 11. Files Changed

All changes are in the frontend. No backend changes.

- `frontend/src/App.tsx` — layout restructure, state lifting, component refactoring
- `frontend/src/index.css` — possible minor additions for card styles, bottom bar

No new files needed. The monolithic App.tsx stays monolithic (splitting into multiple files is out of scope for this redesign).
