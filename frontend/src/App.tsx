import { useState, useEffect, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as Switch from '@radix-ui/react-switch'
import * as Select from '@radix-ui/react-select'
import { api } from './api'
import type { SuspendConfig, ModeInterval } from './types'

// ─── Utilities ──────────────────────────────────────────────────────────────

function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}

function toDate(val: string | number | null | undefined): Date | null {
  if (val == null) return null
  const n = typeof val === 'number' ? val * 1000 : parseFloat(String(val))
  const d = isNaN(n) ? new Date(String(val)) : new Date(n)
  return isNaN(d.getTime()) ? null : d
}

function formatLastRender(val: string | number | null | undefined): string {
  const d = toDate(val)
  if (!d) return '—'
  const today = new Date()
  const isToday = d.toDateString() === today.toDateString()
  const time = d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return `today ${time}`
  return d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short' }) + ` ${time}`
}

function formatTime(val: string | number | null | undefined): string {
  const d = toDate(val)
  if (!d) return '—'
  return d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
}

function formatUptime(s: number): string {
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60) % 60
  const h = Math.floor(s / 3600)
  if (h === 0) return `${m}m`
  return `${h}h ${m}m`
}

const DAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

// ─── Taglines ─────────────────────────────────────────────────────────────────

const TAGLINES = [
  "The best thing a screen can do is earn its update.",
  "One Pi. One wall. An unreasonable amount of thought.",
  "Updates every five minutes. Refreshes never.",
  "Literary quotes and slow cinema, sharing a wall politely.",
  "A clock that reads. A cinema that waits. One device that doesn't care.",
  "The Pis were already there. The reasoning was air-tight.",
  "Each frame costs 30 seconds of e-ink patience.",
  "Typeset in Taviraj. Rendered on a Tuesday.",
  "Six languages. Seven colours. Zero hurry.",
  "The screen earns its right to exist, one minute at a time.",
  "Built to impress guests who didn't ask to be impressed.",
  "A confession of over-engineering disguised as a clock.",
  "SlowMovie: because films deserve to be watched at 1 frame per minute.",
  "No streaming. No notifications. Just the wall, being interesting.",
  "It updates less often than your opinions. And it's more reliable.",
  "Borges, Calvino, Woolf — and a random Wikipedia article. Niche.",
  "Powered by a chip the size of a stamp and a questionable amount of free time.",
  "A dashboard for a device that doesn't need one.",
  "The font survived the migration. Not everything does.",
  "Four buttons on the side. None of them labelled correctly.",
]

const TAGLINE = TAGLINES[Math.floor(Math.random() * TAGLINES.length)]

// ─── Mode Registry ──────────────────────────────────────────────────────────

interface ModeInfo {
  id: string
  label: string
  icon: string
  color: string
  available: boolean
}

const ALL_MODES: ModeInfo[] = [
  { id: 'litclock',  label: 'LitClock',  icon: '🕐', color: '#2563EB', available: true },
  { id: 'slowmovie', label: 'SlowMovie', icon: '🎬', color: '#D97706', available: true },
  { id: 'wikipedia', label: 'Wikipedia', icon: '📖', color: '#DC2626', available: true },
  { id: 'weather',   label: 'Weather',   icon: '🌤', color: '#059669', available: true },
  { id: 'museo',     label: 'Museo',     icon: '🎨', color: '#7C3AED', available: true },
  { id: 'koan',      label: 'Koan',      icon: '禅', color: '#4F46E5', available: true },
  { id: 'cucina',    label: 'Cucina',    icon: '🍽', color: '#EA580C', available: true },
]

const MODE_MAP = Object.fromEntries(ALL_MODES.map(m => [m.id, m]))

function getModeInfo(id: string): ModeInfo {
  return MODE_MAP[id] ?? { id, label: id, icon: '?', color: '#9E9EB5', available: false }
}

// ─── Language names ──────────────────────────────────────────────────────────

const LANG_NAMES: Record<string, string> = {
  it: 'Italiano',
  en: 'English',
  de: 'Deutsch',
  es: 'Español',
  fr: 'Français',
  pt: 'Português',
}

function langLabel(code: string): string {
  return LANG_NAMES[code] ?? code
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

// ─── Noise Canvas ────────────────────────────────────────────────────────────

function NoiseCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    let active = true
    const W = canvas.width, H = canvas.height
    const draw = () => {
      if (!active) return
      const img = ctx.createImageData(W, H)
      const d = img.data
      for (let i = 0; i < d.length; i += 4) {
        const on = Math.random() > 0.42
        const v = on ? Math.floor(Math.random() * 180 + 60) : 0
        d[i] = d[i + 1] = d[i + 2] = v
        d[i + 3] = on ? Math.floor(Math.random() * 55 + 18) : 0
      }
      ctx.putImageData(img, 0, 0)
      setTimeout(draw, 75)
    }
    draw()
    return () => { active = false }
  }, [])
  return (
    <canvas
      ref={canvasRef}
      width={100}
      height={62}
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ imageRendering: 'pixelated', opacity: 0.26 }}
    />
  )
}

// ─── Radio Waves ──────────────────────────────────────────────────────────────

function RadioWaves({ color }: { color: string }) {
  return (
    <div className="relative flex items-center justify-center" style={{ width: 56, height: 56 }}>
      {[0, 1, 2, 3].map(i => (
        <div
          key={i}
          className="absolute rounded-full animate-radio-expand"
          style={{
            width: 12,
            height: 12,
            border: `1.5px solid ${color}`,
            animationDelay: `${i * 0.55}s`,
            opacity: 0,
          }}
        />
      ))}
      <div className="rounded-full" style={{ width: 7, height: 7, backgroundColor: color, opacity: 0.85 }} />
    </div>
  )
}

// ─── Rendering Overlay ───────────────────────────────────────────────────────

function RenderingOverlay({ mode }: { mode: string }) {
  const info = getModeInfo(mode)
  return (
    <div
      className="absolute inset-0 z-20 rounded-sm overflow-hidden flex items-center justify-center"
      style={{ backgroundColor: '#1A1A2E' }}
    >
      <NoiseCanvas />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.18) 0px, rgba(0,0,0,0.18) 1px, transparent 1px, transparent 3px)',
          zIndex: 1,
        }}
      />
      <div
        className="absolute left-0 right-0 pointer-events-none"
        style={{
          height: '80px',
          background: 'linear-gradient(to bottom, transparent, rgba(255,29,165,0.06) 30%, rgba(255,29,165,0.13) 50%, rgba(255,29,165,0.06) 70%, transparent)',
          top: '-80px',
          animation: 'scanSweep 3.2s linear infinite',
          zIndex: 2,
        }}
      />
      <div className="relative flex flex-col items-center gap-3" style={{ zIndex: 3 }}>
        <div
          className="font-title animate-flicker select-none"
          style={{
            fontSize: '3.2rem',
            lineHeight: 1.1,
            color: '#FFFFFF',
            textShadow: `0 0 24px ${info.color}55, 0 0 60px ${info.color}22`,
          }}
        >
          {info.label}
        </div>
        <div
          className="font-display tracking-[0.4em] uppercase"
          style={{ fontSize: '15px', color: `${info.color}99` }}
        >
          TUNING
        </div>
        <RadioWaves color={info.color} />
      </div>
      <div
        className="absolute inset-0 pointer-events-none rounded-sm"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(26,26,46,0.65) 100%)',
          zIndex: 4,
        }}
      />
    </div>
  )
}

// ─── Frame Preview ───────────────────────────────────────────────────────────

function FramePreview({ refreshKey, waiting, waitingMode }: { refreshKey: number; waiting: boolean; waitingMode: string }) {
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)
  const src = `/api/frame?t=${refreshKey}`

  useEffect(() => {
    setLoaded(false)
    setErrored(false)
  }, [refreshKey])

  return (
    <div className="relative w-full rounded-sm overflow-hidden" style={{ aspectRatio: '5/3', border: '1px solid rgba(0,0,0,0.08)' }}>
      {waiting && <RenderingOverlay mode={waitingMode} />}

      {!waiting && !loaded && !errored && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-deep">
          <div className="w-px h-8 bg-accent/30 animate-pulse-accent" />
          <span className="label tracking-[0.3em]">loading frame</span>
        </div>
      )}

      {!waiting && errored && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-deep">
          <span className="font-display text-3xl text-muted font-bold tracking-widest uppercase">no signal</span>
          <span className="label">frame not available</span>
        </div>
      )}

      {!waiting && (
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
      )}
    </div>
  )
}

// ─── Playlist Editor ────────────────────────────────────────────────────────

function GripIcon() {
  return (
    <svg width="8" height="12" viewBox="0 0 8 12" fill="currentColor">
      <circle cx="2" cy="2" r="1.2" />
      <circle cx="6" cy="2" r="1.2" />
      <circle cx="2" cy="6" r="1.2" />
      <circle cx="6" cy="6" r="1.2" />
      <circle cx="2" cy="10" r="1.2" />
      <circle cx="6" cy="10" r="1.2" />
    </svg>
  )
}

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      width="12" height="12" viewBox="0 0 12 12" fill="none"
      className={spinning ? 'animate-spin' : ''}
    >
      <path d="M10.5 6a4.5 4.5 0 1 1-1.32-3.18" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M9 1.5h2.25V3.75" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function PlaylistEditor({
  playlist,
  rotationInterval,
  currentMode,
  onSave,
  saving,
  onRefresh,
  refreshing,
}: {
  playlist: string[]
  rotationInterval: number
  currentMode: string
  onSave: (modes: string[], interval: number) => void
  saving: boolean
  onRefresh: () => void
  refreshing: boolean
}) {
  const [items, setItems] = useState<string[]>([])
  const [enabled, setEnabled] = useState<Set<string>>(new Set())
  const [interval, setIntervalVal] = useState(Math.round(rotationInterval / 60))
  const [saved, setSaved] = useState(false)
  const [dragIdx, setDragIdx] = useState<number | null>(null)
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const lastSyncedRef = useRef('')

  useEffect(() => {
    if (playlist.length === 0) return
    const key = playlist.join(',') + ':' + rotationInterval
    if (lastSyncedRef.current === key) return
    lastSyncedRef.current = key

    const orderedEnabled = [...playlist]
    const disabledAvailable = ALL_MODES
      .filter(m => m.available && !playlist.includes(m.id))
      .map(m => m.id)
    const comingSoon = ALL_MODES.filter(m => !m.available).map(m => m.id)

    setItems([...orderedEnabled, ...disabledAvailable, ...comingSoon])
    setEnabled(new Set(playlist))
    setIntervalVal(Math.round(rotationInterval / 60))
  }, [playlist, rotationInterval])

  const toggleMode = (id: string) => {
    const info = getModeInfo(id)
    if (!info.available) return
    setEnabled(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        if (next.size <= 1) return prev
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleDragStart = (e: React.DragEvent, idx: number) => {
    setDragIdx(idx)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    if (dragOverIdx !== idx) setDragOverIdx(idx)
  }

  const handleDrop = (e: React.DragEvent, idx: number) => {
    e.preventDefault()
    if (dragIdx === null || dragIdx === idx) return
    setItems(prev => {
      const next = [...prev]
      const [removed] = next.splice(dragIdx, 1)
      const insertIdx = dragIdx < idx ? idx - 1 : idx
      next.splice(insertIdx, 0, removed)
      return next
    })
    setDragIdx(null)
    setDragOverIdx(null)
  }

  const handleDragEnd = () => {
    setDragIdx(null)
    setDragOverIdx(null)
  }

  const handleSave = () => {
    const orderedEnabled = items.filter(id => enabled.has(id))
    onSave(orderedEnabled, interval * 60)
    setSaved(true)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setSaved(false), 2500)
  }

  const enabledCount = enabled.size
  const isRotating = enabledCount > 1

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        {items.map((id, idx) => {
          const info = getModeInfo(id)
          const isEnabled = enabled.has(id)
          const isCurrent = id === currentMode
          const isComingSoon = !info.available
          const isDragging = dragIdx === idx
          const showDivider = dragOverIdx === idx && dragOverIdx !== dragIdx

          return (
            <div key={id}>
              {showDivider && (
                <div className="h-0.5 rounded-full mx-3 my-0.5 bg-accent" style={{ boxShadow: '0 0 6px rgba(255,29,165,0.35)' }} />
              )}
              <div
                draggable={!isComingSoon}
                onDragStart={e => handleDragStart(e, idx)}
                onDragOver={e => handleDragOver(e, idx)}
                onDrop={e => handleDrop(e, idx)}
                onDragEnd={handleDragEnd}
                className={cx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-150',
                  isComingSoon
                    ? 'opacity-35'
                    : isEnabled
                      ? 'hover:bg-surface-hover'
                      : 'opacity-50 hover:opacity-70',
                  isDragging ? 'opacity-40 scale-[0.98]' : '',
                )}
                style={{
                  border: isEnabled && !isComingSoon
                    ? `1px solid rgba(0,0,0,0.10)`
                    : '1px solid rgba(0,0,0,0.06)',
                  borderLeft: isEnabled && !isComingSoon
                    ? `3px solid ${info.color}`
                    : '3px solid transparent',
                  backgroundColor: isEnabled && !isComingSoon ? 'rgba(255,29,165,0.04)' : undefined,
                  cursor: isComingSoon ? 'default' : 'grab',
                }}
              >
                {!isComingSoon && (
                  <div className="text-muted flex-shrink-0 select-none">
                    <GripIcon />
                  </div>
                )}

                <button
                  onClick={() => toggleMode(id)}
                  disabled={isComingSoon}
                  className={cx(
                    'w-[20px] h-[20px] rounded-xs flex items-center justify-center flex-shrink-0 transition-all duration-200',
                    isComingSoon ? 'cursor-not-allowed' : 'cursor-pointer',
                  )}
                  style={{
                    border: isEnabled ? `1px solid ${info.color}` : '1px solid rgba(0,0,0,0.12)',
                    backgroundColor: isEnabled ? info.color : 'transparent',
                  }}
                >
                  {isEnabled && (
                    <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                      <path d="M1 4l2.5 2.5L9 1" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>

                <span className="text-sm flex-shrink-0 w-5 text-center" style={{ color: isEnabled ? info.color : '#9E9EB5' }}>
                  {info.icon}
                </span>
                <span
                  className={cx(
                    'font-display text-[15px] flex-1',
                    isEnabled && !isComingSoon ? 'font-semibold' : '',
                    isComingSoon ? 'text-muted' : 'text-primary',
                  )}
                  style={{ color: isEnabled && !isComingSoon ? info.color : undefined }}
                >
                  {info.label}
                </span>

                {isCurrent && (
                  <span
                    className="font-mono text-[9px] font-bold tracking-[0.1em] px-2 py-0.5 rounded-xs"
                    style={{ color: info.color, backgroundColor: `${info.color}18` }}
                  >
                    NOW
                  </span>
                )}

                {isComingSoon && (
                  <span className="font-mono text-[9px] font-bold uppercase tracking-[0.1em] text-muted px-2 py-0.5 rounded-xs bg-surface">
                    soon
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {isRotating && (
        <div className="flex items-center gap-3 px-1 animate-fade-in">
          <span className="label flex-shrink-0">Rotation</span>
          <input
            type="number"
            min={1}
            max={60}
            value={interval}
            onChange={e => setIntervalVal(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-16 bg-surface rounded-xs text-primary font-mono text-sm px-2 py-1.5 outline-none transition-all duration-200 text-center"
            style={{ border: '1px solid rgba(0,0,0,0.10)' }}
            onFocus={e => (e.target.style.borderColor = '#FF1DA5')}
            onBlur={e => (e.target.style.borderColor = 'rgba(0,0,0,0.10)')}
          />
          <span className="label">min</span>
          <span className="label ml-auto" style={{ color: '#2563EB' }}>
            {enabledCount} modes · {interval * enabledCount} min cycle
          </span>
        </div>
      )}

      <div className="flex items-center gap-2 pt-1 flex-wrap">
        <button
          onClick={handleSave}
          disabled={saving}
          className="font-display text-xs font-bold uppercase tracking-widest px-5 py-2.5 rounded-xs bg-accent text-white hover:bg-accent-hover transition-all duration-200 disabled:opacity-50 disabled:cursor-wait"
        >
          {saving ? '…' : 'Save'}
        </button>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className={cx(
            'flex items-center gap-2 font-display text-xs font-bold uppercase tracking-widest',
            'px-4 py-2.5 rounded-xs transition-all duration-200 outline-none',
            refreshing
              ? 'text-accent/50 cursor-wait'
              : 'text-secondary hover:text-accent cursor-pointer',
          )}
          style={{ border: '1px solid rgba(0,0,0,0.08)' }}
        >
          <RefreshIcon spinning={refreshing} />
          {refreshing ? 'Rendering…' : 'Force refresh'}
        </button>
        {saved && (
          <span className="label animate-fade-in" style={{ color: '#01B574' }}>✓</span>
        )}
      </div>
    </div>
  )
}

// ─── Suspend Form ────────────────────────────────────────────────────────────

function SuspendForm({ initial }: { initial?: SuspendConfig }) {
  const qc = useQueryClient()
  const [enabled, setEnabled] = useState(false)
  const [activeFrom, setActiveFrom] = useState('09:00')
  const [activeTo, setActiveTo] = useState('18:00')
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6])

  const syncedRef = useRef(false)
  useEffect(() => {
    if (!initial || syncedRef.current) return
    setEnabled(initial.enabled)
    setActiveFrom(initial.end ?? '09:00')
    setActiveTo(initial.start ?? '18:00')
    const suspendDays = initial.days ?? []
    setDays([0,1,2,3,4,5,6].filter(d => !suspendDays.includes(d)))
    syncedRef.current = true
  }, [initial])
  const [saved, setSaved] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  const mut = useMutation({
    mutationFn: () => api.suspend({
      enabled,
      start: activeTo,
      end: activeFrom,
      days: [0,1,2,3,4,5,6].filter(d => !days.includes(d)),
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
          <div className="label mb-1">On from</div>
          <input
            type="time"
            value={activeFrom}
            onChange={e => setActiveFrom(e.target.value)}
            className="w-full bg-surface rounded-xs text-primary font-mono text-sm px-3 py-2 outline-none transition-all duration-200"
            style={{ border: '1px solid rgba(0,0,0,0.10)' }}
            onFocus={e => (e.target.style.borderColor = '#FF1DA5')}
            onBlur={e => (e.target.style.borderColor = 'rgba(0,0,0,0.10)')}
          />
        </div>
        <span className="label pb-2" style={{ color: '#FF1DA5' }}>→</span>
        <div>
          <div className="label mb-1">Off at</div>
          <input
            type="time"
            value={activeTo}
            onChange={e => setActiveTo(e.target.value)}
            className="w-full bg-surface rounded-xs text-primary font-mono text-sm px-3 py-2 outline-none transition-all duration-200"
            style={{ border: '1px solid rgba(0,0,0,0.10)' }}
            onFocus={e => (e.target.style.borderColor = '#FF1DA5')}
            onBlur={e => (e.target.style.borderColor = 'rgba(0,0,0,0.10)')}
          />
        </div>
      </div>

      <div>
        <div className="label mb-2">Active days</div>
        <div className="flex items-center gap-1.5">
          {DAYS.map((d, i) => (
            <button
              key={i}
              onClick={() => toggleDay(i)}
              className={cx(
                'w-9 h-9 text-[12px] font-display font-bold rounded-xs transition-all duration-200 outline-none',
                days.includes(i)
                  ? 'bg-accent text-white'
                  : 'text-tertiary hover:text-primary cursor-pointer',
              )}
              style={{ border: days.includes(i) ? '1px solid #FF1DA5' : '1px solid rgba(0,0,0,0.10)' }}
            >
              {d}
            </button>
          ))}
          <button
            onClick={() => mut.mutate()}
            disabled={mut.isPending}
            className="ml-auto font-display text-xs font-bold uppercase tracking-widest px-4 py-2 rounded-xs bg-accent text-white hover:bg-accent-hover transition-all duration-200 disabled:opacity-50 disabled:cursor-wait"
          >
            {mut.isPending ? '…' : 'Save'}
          </button>
          {saved && (
            <span className="label animate-fade-in" style={{ color: '#01B574' }}>✓</span>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Interval Controls ───────────────────────────────────────────────────────

function fmtInterval(s: number): string {
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem === 0 ? `${m} min` : `${m}m ${rem}s`
}

function IntervalRow({
  modeName,
  data,
  color,
  icon,
}: {
  modeName: string
  data: ModeInterval
  color: string
  icon: string
}) {
  const qc = useQueryClient()
  const [minutes, setMinutes] = useState(Math.round(data.effective / 60))

  useEffect(() => {
    setMinutes(Math.round(data.effective / 60))
  }, [data.effective])

  const setMut = useMutation({
    mutationFn: () => api.setInterval(modeName, minutes * 60),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['status'] }),
  })

  const resetMut = useMutation({
    mutationFn: () => api.resetInterval(modeName),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['status'] })
      setMinutes(Math.round(data.default / 60))
    },
  })

  return (
    <div className="flex items-center gap-3 py-2.5" style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
      <span className="text-sm" style={{ color }}>{icon}</span>
      <span className="font-display text-sm flex-shrink-0 w-20" style={{ color }}>{modeName}</span>
      <input
        type="number"
        min={1}
        max={1440}
        value={minutes}
        onChange={e => setMinutes(Math.max(1, parseInt(e.target.value) || 1))}
        className="w-16 bg-surface rounded-xs text-primary font-mono text-sm px-2 py-1.5 outline-none transition-all duration-200 text-center"
        style={{ border: '1px solid rgba(0,0,0,0.10)' }}
        onFocus={e => (e.target.style.borderColor = '#FF1DA5')}
        onBlur={e => (e.target.style.borderColor = 'rgba(0,0,0,0.10)')}
      />
      <span className="label">min</span>
      <button
        onClick={() => setMut.mutate()}
        disabled={setMut.isPending}
        className="font-display text-[11px] font-bold uppercase tracking-widest px-3 py-1.5 rounded-xs text-secondary hover:text-accent transition-all duration-200 disabled:opacity-50"
        style={{ border: '1px solid rgba(0,0,0,0.08)' }}
      >
        {setMut.isPending ? '…' : 'Set'}
      </button>
      {data.overridden && (
        <button
          onClick={() => resetMut.mutate()}
          disabled={resetMut.isPending}
          className="label hover:text-danger transition-colors"
          style={{ color: '#EE5D50' }}
        >
          reset
        </button>
      )}
      <span className="label ml-auto text-right font-mono">
        {data.overridden
          ? <span style={{ color }}>● {fmtInterval(data.effective)}</span>
          : <span className="text-muted">{fmtInterval(data.effective)}</span>
        }
      </span>
    </div>
  )
}

// ─── Language Selector ───────────────────────────────────────────────────────

function LanguageSelector({ current }: { current?: string }) {
  const qc = useQueryClient()
  const [localLang, setLocalLang] = useState<string | null>(null)

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

  const displayLang = localLang ?? current ?? langs[0]

  return (
    <div className="flex items-center gap-4">
      <span className="label flex-shrink-0">Language</span>
      <Select.Root
        value={displayLang}
        onValueChange={lang => { setLocalLang(lang); mut.mutate(lang) }}
      >
        <Select.Trigger
          data-radix-select-trigger=""
          className="flex-1 max-w-xs"
          aria-label="Language"
        >
          <Select.Value>
            {langLabel(displayLang)}
          </Select.Value>
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
                  <Select.ItemText>{langLabel(l)}</Select.ItemText>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
      {mut.isPending && <span className="label animate-fade-in" style={{ color: '#FF1DA5' }}>…</span>}
      {!mut.isPending && mut.isSuccess && <span className="label animate-fade-in" style={{ color: '#01B574' }}>✓</span>}
    </div>
  )
}

// ─── Weather Settings ────────────────────────────────────────────────────────

// ─── Koan Archive ───────────────────────────────────────────────────────────

interface KoanHaiku {
  id: number
  timestamp: string
  lines: string[]
  seed_word: string
  author_name: string
  source: string
  generation_time_ms: number
  model?: string
  total_tokens?: number
}

function KoanArchivePanel({ onViewAll }: { onViewAll: () => void }) {
  const { data } = useQuery({
    queryKey: ['koan-archive'],
    queryFn: async () => {
      const r = await fetch(`/api/koan/archive`)
      return r.json() as Promise<{ haiku: KoanHaiku[]; count: number }>
    },
    refetchInterval: 60_000,
  })

  const count = data?.count ?? 0
  if (count === 0) return null

  const latest = data?.haiku?.[0]

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="label">Koan archive</h2>
        <button
          onClick={onViewAll}
          className="font-mono text-xs text-accent hover:text-accent-hover transition-colors"
        >
          {count} haiku — view all →
        </button>
      </div>

      {latest && (
        <div className="p-3 rounded-lg border border-border/50 bg-surface/50">
          <div className="font-mono text-[10px] text-muted mb-2">{latest.seed_word} · №{latest.id}</div>
          <div style={{ fontFamily: 'Georgia, "Times New Roman", serif', fontStyle: 'italic' }} className="text-sm text-primary leading-relaxed">
            {latest.lines.map((line, i) => <div key={i}>{line}</div>)}
          </div>
          <div className="mt-2 font-mono text-xs text-muted/80">— {latest.author_name}</div>
        </div>
      )}
    </section>
  )
}


function KoanArchivePage({ onBack }: { onBack: () => void }) {
  const [search, setSearch] = useState('')
  const [visibleCount, setVisibleCount] = useState(30)

  const { data, isLoading } = useQuery({
    queryKey: ['koan-archive'],
    queryFn: async () => {
      const r = await fetch(`/api/koan/archive`)
      return r.json() as Promise<{ haiku: KoanHaiku[]; count: number }>
    },
  })

  const count = data?.count ?? 0
  const allHaiku = data?.haiku ?? []

  const filtered = search.trim()
    ? allHaiku.filter(h =>
        h.seed_word.toLowerCase().includes(search.toLowerCase()) ||
        h.author_name.toLowerCase().includes(search.toLowerCase()) ||
        h.lines.some(l => l.toLowerCase().includes(search.toLowerCase()))
      )
    : allHaiku

  const visible = filtered.slice(0, visibleCount)
  const hasMore = visibleCount < filtered.length

  return (
    <div className="min-h-screen" style={{ background: '#121225' }}>
      {/* ── Header ── */}
      <header className="sticky top-0 z-10 backdrop-blur-md" style={{ background: 'rgba(18,18,37,0.92)' }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <button
                onClick={onBack}
                className="font-mono text-xs text-muted hover:text-accent transition-colors"
              >
                ← dashboard
              </button>
              <h1 className="font-title text-2xl sm:text-3xl text-white/90">Koan Archive</h1>
              <span
                className="font-mono text-xs px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(255,29,165,0.10)', color: '#FF1DA5' }}
              >
                {count}
              </span>
            </div>
            <a
              href="/api/koan/archive/export"
              download
              className="font-mono text-xs px-4 py-2 rounded-md transition-all duration-200 hover:shadow-lg"
              style={{
                background: '#FF1DA5',
                color: '#FFFFFF',
                fontWeight: 700,
              }}
            >
              Export ZIP ↓
            </a>
          </div>

          {/* ── Search ── */}
          <div className="mt-3">
            <input
              type="text"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setVisibleCount(30) }}
              placeholder="search themes, pen names, words…"
              className="w-full sm:w-80 px-3 py-2 rounded-md font-mono text-xs text-white/90 placeholder:text-white/30 outline-none transition-colors"
              style={{
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.10)',
              }}
            />
          </div>
        </div>
        <div style={{ height: 1, background: 'rgba(255,255,255,0.08)' }} />
      </header>

      {/* ── Grid ── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {isLoading ? (
          <p className="font-mono text-sm text-muted text-center py-20">loading…</p>
        ) : filtered.length === 0 ? (
          <p className="font-mono text-sm text-muted text-center py-20">
            {search ? 'no haiku match your search' : 'no haiku yet'}
          </p>
        ) : (
          <>
            <div
              className="gap-4"
              style={{
                columns: '280px',
                columnGap: '16px',
              }}
            >
              {visible.map((h, idx) => (
                <HaikuCard key={h.id} haiku={h} index={idx} />
              ))}
            </div>

            {hasMore && (
              <div className="flex justify-center pt-8 pb-4">
                <button
                  onClick={() => setVisibleCount(v => v + 30)}
                  className="font-mono text-xs px-6 py-2 rounded-md transition-all duration-200 hover:shadow-lg"
                  style={{
                    background: 'rgba(255,29,165,0.06)',
                    border: '1px solid rgba(255,29,165,0.12)',
                    color: '#FF1DA5',
                  }}
                >
                  load more ({filtered.length - visibleCount} remaining)
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="text-center py-8">
        <span className="font-mono text-[10px] text-muted/40">
          TaleVision · Koan · {count} haiku preserved
        </span>
      </footer>
    </div>
  )
}


function HaikuCard({ haiku: h, index }: { haiku: KoanHaiku; index: number }) {
  const genSec = (h.generation_time_ms / 1000).toFixed(1)
  const modelShort = h.model?.split('/').pop()?.replace('llama-', '').replace('-versatile', '') ?? h.source
  const date = new Date(h.timestamp)
  const dateStr = !isNaN(date.getTime())
    ? date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
    : ''

  return (
    <div
      className="mb-4 rounded-lg overflow-hidden transition-all duration-300 hover:-translate-y-0.5"
      style={{
        breakInside: 'avoid',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.06)',
        boxShadow: '0 2px 8px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03)',
        animationDelay: `${Math.min(index * 30, 300)}ms`,
      }}
    >
      <div className="p-4">
        {/* Theme header */}
        <div className="flex items-start justify-between mb-3">
          <span
            className="font-mono text-[10px] leading-tight"
            style={{ color: 'rgba(255,29,165,0.35)' }}
          >
            {h.seed_word}
          </span>
          <span
            className="font-mono text-[10px] shrink-0 ml-2"
            style={{ color: 'rgba(255,255,255,0.2)' }}
          >
            №{h.id}
          </span>
        </div>

        {/* Haiku lines */}
        <div
          className="leading-relaxed mb-3"
          style={{
            fontFamily: 'Georgia, "Crimson Text", "Times New Roman", serif',
            fontStyle: 'italic',
            fontSize: '14px',
            lineHeight: '1.7',
            color: '#FAF8F5',
          }}
        >
          {h.lines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>

        {/* Pen name */}
        <div
          className="font-mono text-xs mb-2"
          style={{ color: 'rgba(255,29,165,0.65)' }}
        >
          — {h.author_name}
        </div>

        {/* Metadata footer */}
        <div
          className="flex items-center justify-between pt-2"
          style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
        >
          <span className="font-mono text-[9px]" style={{ color: 'rgba(255,255,255,0.15)' }}>
            {modelShort} · {genSec}s · {h.total_tokens ?? '?'}tok
          </span>
          <span className="font-mono text-[9px]" style={{ color: 'rgba(255,255,255,0.15)' }}>
            {dateStr}
          </span>
        </div>
      </div>
    </div>
  )
}


function WeatherSettings({ currentLocation }: { currentLocation?: string }) {
  const qc = useQueryClient()
  const [input, setInput] = useState(currentLocation ?? '')
  const [suggestions, setSuggestions] = useState<Array<{ name: string; display: string; lat: number; lon: number }>>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedCoords, setSelectedCoords] = useState<{ lat: number; lon: number } | null>(null)
  const [saved, setSaved] = useState(false)
  const [units, setUnits] = useState('m')
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (currentLocation && !input) setInput(currentLocation)
  }, [currentLocation])

  useEffect(() => {
    api.getWeatherUnits().then(d => setUnits(d.units)).catch(() => {})
  }, [])

  const searchMut = useMutation({
    mutationFn: (q: string) => api.searchWeatherLocation(q),
    onSuccess: (data) => {
      setSuggestions(data.results)
      setShowSuggestions(data.results.length > 0)
    },
  })

  const saveMut = useMutation({
    mutationFn: () => {
      if (!selectedCoords) return Promise.reject(new Error('No city selected'))
      return api.setWeatherLocation(input, selectedCoords.lat, selectedCoords.lon)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['status'] })
      setSaved(true)
      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setSaved(false), 2500)
    },
  })

  const unitsMut = useMutation({
    mutationFn: (u: string) => api.setWeatherUnits(u),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['status'] }),
  })

  const handleInputChange = (val: string) => {
    setInput(val)
    setSelectedCoords(null)
    clearTimeout(debounceRef.current)
    if (val.length >= 2) {
      debounceRef.current = setTimeout(() => searchMut.mutate(val), 400)
    } else {
      setSuggestions([])
      setShowSuggestions(false)
    }
  }

  const selectSuggestion = (s: { name: string; display: string; lat: number; lon: number }) => {
    setInput(s.name)
    setSelectedCoords({ lat: s.lat, lon: s.lon })
    setSuggestions([])
    setShowSuggestions(false)
  }

  const toggleUnits = () => {
    const next = units === 'm' ? 'u' : 'm'
    setUnits(next)
    unitsMut.mutate(next)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="label flex-shrink-0">Location</span>
        <div className="relative flex-1 max-w-xs">
          <input
            type="text"
            value={input}
            onChange={e => handleInputChange(e.target.value)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="City name…"
            className="w-full bg-surface rounded-xs text-primary font-display text-sm px-3 py-2 outline-none transition-all duration-200"
            style={{ border: '1px solid rgba(0,0,0,0.10)' }}
            onFocus={e => (e.target.style.borderColor = '#FF1DA5')}
          />
          {showSuggestions && suggestions.length > 0 && (
            <div
              className="absolute top-full left-0 right-0 mt-1 bg-surface rounded-xs z-50 overflow-hidden"
              style={{ border: '1px solid rgba(0,0,0,0.10)' }}
            >
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => selectSuggestion(s)}
                  className="w-full text-left px-3 py-2 font-display text-sm text-secondary hover:bg-surface-hover hover:text-accent transition-colors"
                >
                  <span className="text-primary">{s.name}</span>
                  <span className="text-muted text-xs ml-2">{s.display}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending || !input.trim() || !selectedCoords}
          className="font-display text-xs font-bold uppercase tracking-widest px-5 py-2.5 rounded-xs bg-accent text-white hover:bg-accent-hover transition-all duration-200 disabled:opacity-50"
        >
          {saveMut.isPending ? 'Saving…' : 'Set location'}
        </button>
        <button
          onClick={toggleUnits}
          className="font-mono text-xs font-bold uppercase tracking-widest px-4 py-2.5 rounded-xs text-secondary hover:text-accent transition-all duration-200"
          style={{ border: '1px solid rgba(0,0,0,0.08)' }}
        >
          {units === 'm' ? '°C · km/h' : '°F · mph'}
        </button>
        {saved && <span className="label animate-fade-in" style={{ color: '#01B574' }}>Saved</span>}
      </div>
    </div>
  )
}

// ─── Divider ────────────────────────────────────────────────────────────────

function Divider() {
  return <div className="border-t border-border" />
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const clock = useClock()
  const qc = useQueryClient()
  const [refreshKey, setRefreshKey] = useState(Date.now())
  const [waitingSince, setWaitingSince] = useState<number | null>(null)
  const [pendingMode, setPendingMode] = useState<string | null>(null)
  const [view, setView] = useState<'dashboard' | 'archive'>('dashboard')
  const waiting = waitingSince !== null

  const { data: status, isError } = useQuery({
    queryKey: ['status'],
    queryFn: api.status,
    refetchInterval: waiting ? 2000 : 12_000,
  })

  useEffect(() => {
    if (!waiting || !waitingSince || !status?.last_update) return
    const lu = typeof status.last_update === 'number'
      ? status.last_update * 1000
      : parseFloat(String(status.last_update))
    if (!isNaN(lu) && lu > waitingSince) {
      setWaitingSince(null)
      setRefreshKey(Date.now())
    }
  }, [status?.last_update, waiting, waitingSince])

  useEffect(() => {
    if (!waiting) return
    const id = setTimeout(() => { setWaitingSince(null); setRefreshKey(Date.now()) }, 120_000)
    return () => clearTimeout(id)
  }, [waiting])

  useEffect(() => {
    if (!waiting) setPendingMode(null)
  }, [waiting])

  const currentMode = status?.mode ?? '—'
  const playlist = status?.playlist ?? [currentMode]
  const rotationInterval = status?.rotation_interval ?? 300
  const isRotating = playlist.length > 1
  const currentModeInfo = getModeInfo(currentMode)

  const playlistMut = useMutation({
    mutationFn: ({ modes, interval }: { modes: string[]; interval: number }) =>
      api.setPlaylist(modes, interval),
    onMutate: ({ modes }) => { setWaitingSince(Date.now()); setPendingMode(modes[0]) },
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['status'] }) },
  })

  const refreshMut = useMutation({
    mutationFn: api.refresh,
    onMutate: () => setWaitingSince(Date.now()),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['status'] }) },
  })

  const handleRefresh = useCallback(() => refreshMut.mutate(), [refreshMut])

  const isSuspended = status?.is_suspended ?? false

  if (view === 'archive') {
    return <KoanArchivePage onBack={() => setView('dashboard')} />
  }

  return (
    <div className="min-h-screen text-primary font-display animate-fade-in">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40" style={{ backgroundColor: '#FAF8F5', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="w-2 h-2 rounded-full bg-accent" style={{ boxShadow: '0 0 10px rgba(255,29,165,0.35)' }} />
            <span className="font-title text-2xl leading-tight text-primary">TaleVision</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="font-mono text-xs text-tertiary tabular-nums">{clock}</span>
            <div className="flex items-center gap-1.5">
              <span
                className={cx(
                  'w-1.5 h-1.5 rounded-full',
                  isError ? 'bg-danger animate-pulse' :
                  isSuspended ? 'bg-tertiary' :
                  'bg-success',
                )}
                style={{
                  boxShadow: isError ? '0 0 6px rgba(238,93,80,0.4)' :
                             !isSuspended && !isError ? '0 0 6px rgba(1,181,116,0.5)' : undefined,
                }}
              />
              <span className="font-mono text-[10px] uppercase tracking-wider"
                style={{
                  color: isError ? '#EE5D50' :
                         isSuspended ? '#9E9EB5' :
                         currentModeInfo.color,
                }}
              >
                {isError ? 'offline' :
                 isSuspended ? 'suspended' :
                 currentMode}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Main content ───────────────────────────────────────────────── */}
      <main className="max-w-2xl mx-auto px-4 py-5 space-y-5">

        <p className="text-xs text-tertiary italic text-center">{TAGLINE}</p>

        <FramePreview refreshKey={refreshKey} waiting={waiting} waitingMode={pendingMode ?? currentMode} />

        {/* Info bar */}
        <div className="flex items-center gap-4 flex-wrap text-xs">
          <span className="text-tertiary">
            <span className="font-mono text-muted">UP</span>{' '}
            <span className="text-secondary font-mono">{formatUptime(status?.uptime_seconds ?? 0)}</span>
          </span>
          <span className="text-tertiary">
            <span className="font-mono text-muted">LAST</span>{' '}
            <span className="text-secondary font-mono">{formatLastRender(status?.last_update)}</span>
          </span>
          {status?.next_wake && (
            <span className="text-tertiary">
              <span className="font-mono text-muted">WAKE</span>{' '}
              <span className="text-secondary font-mono">{formatTime(status.next_wake)}</span>
            </span>
          )}
          {isRotating && (
            <span className="text-tertiary ml-auto">
              {playlist.map(id => getModeInfo(id).icon).join(' → ')}
              <span className="font-mono text-muted ml-1">{fmtInterval(rotationInterval)}</span>
            </span>
          )}
          {status?.video && (
            <span style={{ color: '#D97706' }}>🎬 {status.video}</span>
          )}
        </div>

        <Divider />

        <LanguageSelector current={status?.language ?? undefined} />

        <Divider />

        <section>
          <h2 className="label mb-3">Playlist</h2>
          <PlaylistEditor
            playlist={playlist}
            rotationInterval={rotationInterval}
            currentMode={currentMode}
            onSave={(modes, interval) => playlistMut.mutate({ modes, interval })}
            saving={playlistMut.isPending}
            onRefresh={handleRefresh}
            refreshing={refreshMut.isPending}
          />
        </section>

        <Divider />

        <section>
          <h2 className="label mb-3">Active schedule</h2>
          <SuspendForm initial={status?.suspend} />
        </section>

        {!isRotating && status?.intervals && Object.keys(status.intervals).length > 0 && (
          <>
            <Divider />
            <section>
              <h2 className="label mb-3">Refresh intervals</h2>
              {ALL_MODES.filter(m => m.available && status.intervals![m.id]).map(m => (
                <IntervalRow
                  key={m.id}
                  modeName={m.id}
                  data={status.intervals![m.id]}
                  color={m.color}
                  icon={m.icon}
                />
              ))}
            </section>
          </>
        )}

        {playlist.includes('weather') && (
          <>
            <Divider />
            <section className="animate-fade-in">
              <h2 className="label mb-3">Weather location</h2>
              <WeatherSettings currentLocation={status?.weather_location ?? undefined} />
            </section>
          </>
        )}

        <Divider />
        <KoanArchivePanel onViewAll={() => setView('archive')} />

        <footer className="pt-6 pb-4">
          <Divider />
          <div className="flex items-center justify-between pt-4">
            <span className="font-mono text-[10px] text-secondary">TaleVision · Pi Zero W · 800×480 · e‑ink</span>
            <a
              href="https://github.com/enuzzo/talevision"
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[10px] text-secondary hover:text-accent transition-colors duration-200"
            >
              github/enuzzo ↗
            </a>
          </div>
          <div className="flex flex-col items-center gap-2 pt-6">
            <img
              src="https://netmi.lk/wp-content/uploads/2024/10/netmilk.svg"
              alt="Netmilk Studio"
              className="hover:animate-shake cursor-pointer opacity-90 hover:opacity-100 transition-opacity"
              style={{ width: '110px', height: 'auto' }}
            />
            <span className="font-mono text-[10px] text-secondary text-center">
              MIT · enuzzo + Netmilk Studio · 2024
            </span>
          </div>
        </footer>

      </main>
    </div>
  )
}
