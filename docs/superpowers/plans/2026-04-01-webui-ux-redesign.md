# WebUI UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the TaleVision dashboard for better UX on mobile and desktop — 2-column layout, global Save, fixed action bar, card-based sections.

**Architecture:** All changes in `frontend/src/App.tsx` (monolithic SPA) and `frontend/src/index.css`. State lifting for dirty tracking via onChange callbacks from section components to App. No backend changes, no new dependencies.

**Tech Stack:** React 18 + TypeScript + Tailwind CSS + React Query + Radix UI

**Spec:** `docs/superpowers/specs/2026-04-01-webui-ux-redesign.md`

---

### Task 1: SettingsCard wrapper + remove tagline

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add SettingsCard component** after the Divider component (~line 1698)

```tsx
function SettingsCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      className="rounded-xl p-4 sm:p-5"
      style={{ background: '#FFFAF0', border: '1px solid rgba(0,0,0,0.08)', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
    >
      {title && <h2 className="label mb-3">{title}</h2>}
      {children}
    </section>
  )
}
```

- [ ] **Step 2: Remove TAGLINES array and TAGLINE constant** (lines 49-72)
- [ ] **Step 3: Remove tagline `<p>` from the main render** (the `<p className="text-xs text-tertiary italic text-center mb-5">` line)
- [ ] **Step 4: Build frontend and verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```
git add frontend/src/App.tsx
git commit -m "feat(ui): add SettingsCard component, remove tagline"
```

---

### Task 2: Simplify IntervalRow — remove Set button

**Files:**
- Modify: `frontend/src/App.tsx` — IntervalRow component

- [ ] **Step 1: Refactor IntervalRow to be controlled**

Remove internal `useMutation` for setMut. Accept `value`, `onChange`, `onReset` props instead. Remove Set button. Show reset icon only when overridden.

New signature:
```tsx
function IntervalRow({
  modeName, icon, color, value, defaultVal, overridden, onChange, onReset,
}: {
  modeName: string; icon: string; color: string
  value: number; defaultVal: number; overridden: boolean
  onChange: (minutes: number) => void
  onReset: () => void
})
```

Render: `[icon] [name] ... [input] min [x reset if overridden]` — no Set button, no value display (input IS the value).

- [ ] **Step 2: Build and verify**
- [ ] **Step 3: Commit**

```
git commit -m "refactor(ui): make IntervalRow controlled, remove Set button"
```

---

### Task 3: Refactor PlaylistEditor — remove Save/Refresh buttons

**Files:**
- Modify: `frontend/src/App.tsx` — PlaylistEditor component

- [ ] **Step 1: Remove onSave, saving, onRefresh, refreshing props**

Replace with `onChange` callback. Remove the sticky bottom bar with Save/Force Refresh from PlaylistEditor. The component just manages its list and calls `onChange` when items/enabled/interval change.

New signature:
```tsx
function PlaylistEditor({
  playlist, rotationInterval, currentMode, onChange,
}: {
  playlist: string[]; rotationInterval: number; currentMode: string
  onChange: (data: { modes: string[]; interval: number }) => void
})
```

- [ ] **Step 2: Build and verify**
- [ ] **Step 3: Commit**

```
git commit -m "refactor(ui): make PlaylistEditor controlled, remove save buttons"
```

---

### Task 4: Refactor SuspendForm — remove Save button

**Files:**
- Modify: `frontend/src/App.tsx` — SuspendForm component

- [ ] **Step 1: Make SuspendForm controlled**

Remove internal mutation and Save button. Accept `onChange` callback that fires whenever any field changes.

New signature:
```tsx
function SuspendForm({
  initial, onChange,
}: {
  initial?: SuspendConfig
  onChange: (config: SuspendConfig) => void
})
```

- [ ] **Step 2: Build and verify**
- [ ] **Step 3: Commit**

```
git commit -m "refactor(ui): make SuspendForm controlled, remove save button"
```

---

### Task 5: Refactor WeatherSettings — remove Save, lift state

**Files:**
- Modify: `frontend/src/App.tsx` — WeatherSettings component

- [ ] **Step 1: Make WeatherSettings report changes via onChange**

Keep search-suggest flow internal. Remove "Set location" button. Call `onChange` when user selects a suggestion or toggles units.

New signature:
```tsx
function WeatherSettings({
  currentLocation, onChange,
}: {
  currentLocation?: string
  onChange: (data: { city: string; lat: number; lon: number; units: string }) => void
})
```

- [ ] **Step 2: Build and verify**
- [ ] **Step 3: Commit**

```
git commit -m "refactor(ui): make WeatherSettings controlled, remove save button"
```

---

### Task 6: Global dirty state + Save handler in App

**Files:**
- Modify: `frontend/src/App.tsx` — App component

- [ ] **Step 1: Add pending state refs in App**

Track pending changes for each section:
```tsx
const [pendingPlaylist, setPendingPlaylist] = useState<{modes: string[], interval: number} | null>(null)
const [pendingSchedule, setPendingSchedule] = useState<SuspendConfig | null>(null)
const [pendingIntervals, setPendingIntervals] = useState<Record<string, number>>({})
const [pendingWeather, setPendingWeather] = useState<{city: string, lat: number, lon: number, units: string} | null>(null)
const [pendingLanguage, setPendingLanguage] = useState<string | null>(null)
```

- [ ] **Step 2: Compute dirty state**

```tsx
const isDirty = pendingPlaylist !== null || pendingSchedule !== null
  || Object.keys(pendingIntervals).length > 0 || pendingWeather !== null || pendingLanguage !== null
```

- [ ] **Step 3: Implement handleGlobalSave**

Fire all pending mutations via `Promise.allSettled()`. Clear succeeded fields. Show error for failed ones. Refetch status on success.

- [ ] **Step 4: Add beforeunload guard**

```tsx
useEffect(() => {
  if (!isDirty) return
  const handler = (e: BeforeUnloadEvent) => { e.preventDefault() }
  window.addEventListener('beforeunload', handler)
  return () => window.removeEventListener('beforeunload', handler)
}, [isDirty])
```

- [ ] **Step 5: Add archive navigation guard**

Wrap setView calls with dirty check:
```tsx
const navigateTo = (v: typeof view) => {
  if (isDirty && !window.confirm('You have unsaved changes. Discard?')) return
  setView(v)
}
```

- [ ] **Step 6: Build and verify**
- [ ] **Step 7: Commit**

```
git commit -m "feat(ui): global dirty state tracking and Save handler"
```

---

### Task 7: ActionBar component + header redesign

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add ActionBar component**

Fixed bottom bar for mobile, hidden on lg+:

```tsx
function ActionBar({ dirty, saving, saved, error, onSave, onRefresh, refreshing }: { ... }) {
  // 56px fixed bottom bar with backdrop-blur
  // Save button: ghost when clean, magenta when dirty, green when saved
  // Force Refresh button: always enabled, secondary style
}
```

- [ ] **Step 2: Add save state tracking**

```tsx
const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
```

- [ ] **Step 3: Redesign header**

Desktop: add Save + Force Refresh buttons to the right side of the header (hidden on mobile).
Mobile: compact header (logo + status only), clock moves to status bar below frame.

- [ ] **Step 4: Build and verify**
- [ ] **Step 5: Commit**

```
git commit -m "feat(ui): ActionBar for mobile, header with Save on desktop"
```

---

### Task 8: Main layout restructure — 2-column + cards grid

**Files:**
- Modify: `frontend/src/App.tsx` — main render in App component

- [ ] **Step 1: Restructure top section — 2 columns**

Replace 3-column grid with:
```tsx
<div className="lg:grid lg:grid-cols-[1fr_380px] lg:gap-6 space-y-5 lg:space-y-0">
  {/* Col 1: Frame + status */}
  {/* Col 2: Playlist */}
</div>
```

- [ ] **Step 2: Settings cards grid below**

```tsx
<div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
  <div className="space-y-4">
    <SettingsCard title="Active schedule">...</SettingsCard>
    <SettingsCard title="Preferences">
      {/* Weather + Language combined */}
    </SettingsCard>
  </div>
  <SettingsCard title="Refresh intervals">...</SettingsCard>
</div>
```

- [ ] **Step 3: Archives card full-width**

```tsx
<div className="mt-4">
  <SettingsCard title="Archives">...</SettingsCard>
</div>
```

- [ ] **Step 4: Wire all onChange handlers**

Connect each section component to its corresponding `setPending*` handler.

- [ ] **Step 5: Update max-width to 1200px**

Change `max-w-[1440px]` to `max-w-[1200px]` everywhere.

- [ ] **Step 6: Add bottom spacer for mobile action bar**

```tsx
<div className="h-16 lg:hidden" /> {/* clearance for fixed bottom bar */}
```

- [ ] **Step 7: Compact footer**

Single line, remove Netmilk logo section.

- [ ] **Step 8: Build and verify**
- [ ] **Step 9: Commit**

```
git commit -m "feat(ui): 2-column layout, card-based settings, 1200px max-width"
```

---

### Task 9: Archive pages responsive grid fix

**Files:**
- Modify: `frontend/src/App.tsx` — KoanArchivePage, FloraArchivePage, ElectricSheepArchivePage

- [ ] **Step 1: Replace hardcoded grid-cols-3**

In all three archive pages, change:
```
grid-cols-3
```
to:
```
grid-cols-1 sm:grid-cols-2 lg:grid-cols-3
```

- [ ] **Step 2: Build and verify**
- [ ] **Step 3: Commit**

```
git commit -m "fix(ui): responsive archive grids — 1/2/3 columns by breakpoint"
```

---

### Task 10: Final build + frontend rebuild for Pi

**Files:**
- Build output: `talevision/web/static/dist/`

- [ ] **Step 1: Full build**

Run: `cd frontend && npm run build`
Expected: Clean build, no errors

- [ ] **Step 2: Verify built files**

Run: `ls -la talevision/web/static/dist/`
Expected: index.html + assets/

- [ ] **Step 3: Final commit with built files**

```
git add talevision/web/static/dist/
git commit -m "build: rebuild frontend with UX redesign"
```
