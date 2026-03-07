import { useState, useEffect, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as Switch from '@radix-ui/react-switch'
import * as Select from '@radix-ui/react-select'
import { api } from './api'
import type { SuspendConfig } from './types'

// ─── Utilities ──────────────────────────────────────────────────────────────

function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const diff = Math.floor((Date.now() - d.getTime()) / 1000)
  if (diff < 5) return 'just now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
}

const DAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const MODES = ['litclock', 'slowmovie'] as const
type Mode = typeof MODES[number]

const MODE_LABEL: Record<Mode, string> = {
  litclock: 'LitClock',
  slowmovie: 'SlowMovie',
}

const MODE_ICON: Record<Mode, string> = {
  litclock: '🕐',
  slowmovie: '🎬',
}

const MODE_COLOR: Record<Mode, string> = {
  litclock: '#4a7fa5',
  slowmovie: '#c8923a',
}

// ─── Live Clock ─────────────────────────────────────────────────────────────

function useClock() {
  const [time, setTime] = useState(() => {
    const now = new Date()
    return now.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  })
  useEffect(() => {
    const id = setInterval(() => {
      setTime(new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    }, 1000)
    return () => clearInterval(id)
  }, [])
  return time
}

// ─── Frame Preview ───────────────────────────────────────────────────────────

function FramePreview({ refreshKey }: { refreshKey: number }) {
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)
  const src = `/api/frame?t=${refreshKey}`

  useEffect(() => {
    setLoaded(false)
    setErrored(false)
  }, [refreshKey])

  return (
    <div className="relative w-full bg-black border border-border" style={{ aspectRatio: '5/3' }}>
      {/* Matte frame lines */}
      <div className="absolute inset-[6px] border border-border/40 pointer-events-none z-10" />

      {!loaded && !errored && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
          <div className="w-px h-8 bg-accent/30 animate-pulse-amber" />
          <span className="label tracking-[0.3em]">loading frame</span>
        </div>
      )}

      {errored && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
          <span className="font-display text-3xl text-secondary/40 font-bold tracking-widest uppercase">no signal</span>
          <span className="label">frame not available</span>
        </div>
      )}

      <img
        src={src}
        alt="Current frame"
        className={cx(
          'absolute inset-0 w-full h-full object-contain transition-opacity duration-500',
          loaded ? 'opacity-100' : 'opacity-0',
        )}
        onLoad={() => setLoaded(true)}
        onError={() => { setLoaded(false); setErrored(true) }}
      />
    </div>
  )
}

// ─── Mode Selector ───────────────────────────────────────────────────────────

function ModeSelector({
  current,
  onSwitch,
  switching,
}: {
  current: string
  onSwitch: (m: Mode) => void
  switching: boolean
}) {
  return (
    <div className="flex items-center gap-8">
      {MODES.map(m => {
        const active = current === m
        const color = MODE_COLOR[m]
        return (
          <button
            key={m}
            onClick={() => !active && onSwitch(m)}
            disabled={switching}
            className={cx(
              'relative flex items-center gap-2 font-display text-xl font-semibold pb-1 transition-colors duration-200 outline-none',
              'disabled:cursor-wait',
              active ? 'cursor-default' : 'text-secondary hover:text-primary/70 cursor-pointer',
            )}
            style={{ color: active ? color : undefined }}
          >
            <span className="text-base">{MODE_ICON[m]}</span>
            {MODE_LABEL[m]}
            <span
              className="absolute bottom-0 left-0 h-px transition-all duration-300"
              style={{ width: active ? '100%' : '0%', backgroundColor: color }}
            />
          </button>
        )
      })}
      {switching && (
        <span className="label animate-pulse-amber">switching…</span>
      )}
    </div>
  )
}

// ─── Status Grid ─────────────────────────────────────────────────────────────

function StatusRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2 border-b border-border/50 last:border-0">
      <span className="label flex-shrink-0">{label}</span>
      <span className="value text-right truncate max-w-[220px]">{value}</span>
    </div>
  )
}

// ─── Suspend Form ────────────────────────────────────────────────────────────

function SuspendForm({ initial }: { initial?: SuspendConfig }) {
  const qc = useQueryClient()
  const [enabled, setEnabled] = useState(initial?.enabled ?? false)
  // UI shows "active hours": when the device is ON.
  // The API stores suspend hours (inverse), so we swap start↔end at the boundary.
  // UI activeFrom = API end (suspension ends = device wakes)
  // UI activeTo   = API start (suspension starts = device sleeps)
  const [activeFrom, setActiveFrom] = useState(initial?.end ?? '09:00')
  const [activeTo, setActiveTo] = useState(initial?.start ?? '18:00')
  const [days, setDays] = useState<number[]>(initial?.days ?? [0, 1, 2, 3, 4, 5, 6])
  const [saved, setSaved] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  const mut = useMutation({
    mutationFn: () => api.suspend({
      enabled,
      start: activeTo,    // device goes to sleep at active end
      end: activeFrom,    // device wakes at active start
      days,
    }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['status'] })
      setSaved(true)
      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setSaved(false), 2500)
    },
  })

  const toggleDay = (i: number) =>
    setDays(d => d.includes(i) ? d.filter(x => x !== i) : [...d, i].sort())

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="label">Enabled</span>
        <Switch.Root
          checked={enabled}
          onCheckedChange={setEnabled}
          data-radix-switch-root=""
        >
          <Switch.Thumb data-radix-switch-thumb="" />
        </Switch.Root>
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-2">
        <div>
          <div className="label mb-1">▶ On from (24h)</div>
          <input
            type="time"
            value={activeFrom}
            onChange={e => setActiveFrom(e.target.value)}
            className="w-full bg-surface border border-border text-primary font-mono text-sm px-3 py-2 outline-none focus:border-accent transition-colors"
          />
        </div>
        <span className="label pb-2 text-accent">→</span>
        <div>
          <div className="label mb-1">⏹ Off at (24h)</div>
          <input
            type="time"
            value={activeTo}
            onChange={e => setActiveTo(e.target.value)}
            className="w-full bg-surface border border-border text-primary font-mono text-sm px-3 py-2 outline-none focus:border-accent transition-colors"
          />
        </div>
      </div>

      <div>
        <div className="label mb-2">Active days</div>
        <div className="flex gap-1.5">
          {DAYS.map((d, i) => (
            <button
              key={i}
              onClick={() => toggleDay(i)}
              className={cx(
                'w-8 h-8 text-[11px] font-mono font-medium transition-all duration-150 outline-none',
                days.includes(i)
                  ? 'bg-accent text-bg'
                  : 'bg-surface border border-border text-secondary hover:border-accent/50 hover:text-primary',
              )}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={() => mut.mutate()}
          disabled={mut.isPending}
          className="font-mono text-xs uppercase tracking-widest px-4 py-2 bg-surface border border-border text-primary hover:border-accent hover:text-accent transition-all duration-150 disabled:opacity-50 disabled:cursor-wait"
        >
          {mut.isPending ? 'Saving…' : 'Save schedule'}
        </button>
        {saved && (
          <span className="label text-success animate-fade-in">Saved</span>
        )}
      </div>
    </div>
  )
}

// ─── Language Selector ───────────────────────────────────────────────────────

function LanguageSelector({ current }: { current?: string }) {
  const qc = useQueryClient()
  const { data: langData } = useQuery({
    queryKey: ['languages'],
    queryFn: api.languages,
    staleTime: Infinity,
  })

  const mut = useMutation({
    mutationFn: (lang: string) => api.setLanguage(lang),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['status'] }),
  })

  const langs = langData?.languages ?? []
  if (!langs.length) return null

  return (
    <div className="flex items-center gap-4">
      <span className="label flex-shrink-0">Language</span>
      <Select.Root
        value={current ?? langs[0]}
        onValueChange={lang => mut.mutate(lang)}
      >
        <Select.Trigger
          data-radix-select-trigger=""
          className="flex-1"
          aria-label="Language"
        >
          <Select.Value />
          <Select.Icon>
            <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
              <path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Select.Icon>
        </Select.Trigger>
        <Select.Portal>
          <Select.Content
            data-radix-select-content=""
            position="popper"
            sideOffset={4}
          >
            <Select.Viewport>
              {langs.map(l => (
                <Select.Item key={l} value={l} data-radix-select-item="">
                  <Select.ItemText>{l}</Select.ItemText>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const clock = useClock()
  const qc = useQueryClient()
  const [refreshKey, setRefreshKey] = useState(Date.now())
  const [optimisticMode, setOptimisticMode] = useState<string | null>(null)

  const { data: status, isError } = useQuery({
    queryKey: ['status'],
    queryFn: api.status,
    refetchInterval: 12_000,
  })

  const currentMode = optimisticMode ?? status?.mode ?? '—'

  const modeMut = useMutation({
    mutationFn: (m: Mode) => api.setMode(m),
    onMutate: (m) => setOptimisticMode(m),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['status'] })
      // Reload preview after mode switch + render time
      setTimeout(() => setRefreshKey(Date.now()), 4000)
    },
    onSettled: () => setOptimisticMode(null),
  })

  const refreshMut = useMutation({
    mutationFn: api.refresh,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['status'] })
      // Pi Zero W needs a few seconds to render
      setTimeout(() => setRefreshKey(Date.now()), 5000)
    },
  })

  const handleRefresh = useCallback(() => refreshMut.mutate(), [refreshMut])

  const isSuspended = status?.suspended ?? false

  return (
    <div className="min-h-screen bg-bg text-primary font-mono animate-fade-in">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-bg/95 backdrop-blur-sm border-b border-border">
        <div className="max-w-4xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-accent" />
            <span className="font-display text-lg font-bold tracking-wide">TaleVision</span>
          </div>
          <div className="flex items-center gap-5">
            <span className="font-mono text-sm text-secondary tabular-nums">{clock}</span>
            <div className="flex items-center gap-2">
              <span
                className={cx(
                  'w-1.5 h-1.5 rounded-full',
                  isError ? 'bg-danger animate-pulse' :
                  isSuspended ? 'bg-secondary' :
                  'bg-success',
                )}
              />
              <span
                className="label"
                style={{
                  color: isError ? '#9a4a4a' :
                         isSuspended ? '#6b6b73' :
                         MODES.includes(currentMode as Mode) ? MODE_COLOR[currentMode as Mode] : undefined,
                }}
              >
                {isError ? 'offline' :
                 isSuspended ? '⏸ suspended' :
                 `${MODE_ICON[currentMode as Mode] ?? ''} ${currentMode}`}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Main content ───────────────────────────────────────────────── */}
      <main className="max-w-4xl mx-auto px-6 py-8 space-y-8">

        {/* Frame Preview */}
        <section>
          <FramePreview refreshKey={refreshKey} />
        </section>

        {/* Mode + Refresh row */}
        <section className="flex items-center justify-between">
          <ModeSelector
            current={currentMode}
            onSwitch={m => modeMut.mutate(m)}
            switching={modeMut.isPending}
          />
          <button
            onClick={handleRefresh}
            disabled={refreshMut.isPending}
            className={cx(
              'flex items-center gap-2 font-mono text-xs uppercase tracking-widest',
              'px-4 py-2 border transition-all duration-150 outline-none',
              refreshMut.isPending
                ? 'border-accent/30 text-accent/50 cursor-wait'
                : 'border-border text-secondary hover:border-accent hover:text-accent cursor-pointer',
            )}
          >
            <svg
              width="12" height="12" viewBox="0 0 12 12" fill="none"
              className={refreshMut.isPending ? 'animate-spin' : ''}
            >
              <path
                d="M10.5 6a4.5 4.5 0 1 1-1.32-3.18"
                stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"
              />
              <path d="M9 1.5h2.25V3.75" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {refreshMut.isPending ? 'Rendering…' : 'Force refresh'}
          </button>
        </section>

        <div className="border-t border-border" />

        {/* Status + Suspend — two-column grid */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-8">

          {/* Status */}
          <div>
            <div className="label mb-4">Status</div>
            <div>
              <StatusRow
                label="Mode"
                value={<span className="font-display text-base font-semibold uppercase tracking-wider">{currentMode}</span>}
              />
              <StatusRow
                label="Suspended"
                value={
                  <span style={{ color: isSuspended ? '#c8923a' : '#4a9a6a' }}>
                    {isSuspended ? '⏸ yes' : '▶ no'}
                  </span>
                }
              />
              <StatusRow
                label="Last render"
                value={formatRelative(status?.last_update)}
              />
              {status?.next_wake && (
                <StatusRow
                  label="Wake at"
                  value={formatTime(status.next_wake)}
                />
              )}
              {status?.video && (
                <StatusRow
                  label="🎬 Film"
                  value={<span className="font-display text-base font-semibold" style={{ color: MODE_COLOR.slowmovie }}>{status.video}</span>}
                />
              )}
              {status?.quote && (
                <StatusRow
                  label="💬 Quote"
                  value={
                    <span className="text-xs text-secondary leading-relaxed text-right">
                      {status.quote.length > 80 ? status.quote.slice(0, 80) + '…' : status.quote}
                    </span>
                  }
                />
              )}
            </div>
          </div>

          {/* Suspend Schedule */}
          <div>
            <div className="label mb-4">Active schedule</div>
            <SuspendForm initial={status?.suspend} />
          </div>

        </section>

        {/* Language selector — only for litclock */}
        {currentMode === 'litclock' && (
          <section className="animate-fade-in">
            <div className="border-t border-border mb-6" />
            <LanguageSelector current={undefined} />
          </section>
        )}

        {/* Footer */}
        <footer className="border-t border-border pt-6 pb-2 flex items-center justify-between">
          <span className="label">TaleVision · Pi Zero W</span>
          <span className="label">800 × 480 · e‑ink</span>
        </footer>

      </main>
    </div>
  )
}
