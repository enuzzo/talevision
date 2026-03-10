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
  { id: 'litclock',  label: 'LitClock',  icon: '🕐', color: '#6B8FA0', available: true },
  { id: 'slowmovie', label: 'SlowMovie', icon: '🎬', color: '#C8974A', available: true },
  { id: 'wikipedia', label: 'Wikipedia', icon: '📖', color: '#CA796D', available: true },
  { id: 'weather',   label: 'Weather',   icon: '🌤', color: '#8DA495', available: true },
]

const MODE_MAP = Object.fromEntries(ALL_MODES.map(m => [m.id, m]))

function getModeInfo(id: string): ModeInfo {
  return MODE_MAP[id] ?? { id, label: id, icon: '?', color: '#978A80', available: false }
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
        const on = Math.random() > 0.5
        const v = on ? Math.floor(Math.random() * 160 + 55) : 0
        d[i] = d[i + 1] = d[i + 2] = v
        d[i + 3] = on ? Math.floor(Math.random() * 26 + 4) : 0
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

// ─── Tuning Gauge ─────────────────────────────────────────────────────────────

function TuningGauge({ color }: { color: string }) {
  // Smaller gauge: pivot at (80, 76), radius 58
  const cx = 80, cy = 76, r = 58
  const numTicks = 11
  const ticks = Array.from({ length: numTicks }, (_, i) => {
    const t = (Math.PI * i) / (numTicks - 1)
    const isMajor = i % 2 === 0
    const innerR = r - (isMajor ? 10 : 6)
    return {
      x1: cx - innerR * Math.cos(t),
      y1: cy - innerR * Math.sin(t),
      x2: cx - r * Math.cos(t),
      y2: cy - r * Math.sin(t),
      isMajor,
    }
  })
  return (
    <svg width="160" height="86" viewBox="0 0 160 82" style={{ overflow: 'visible' }}>
      {/* Arc */}
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none" stroke={color + '30'} strokeWidth="1"
      />
      {/* Baseline */}
      <line x1={cx - r - 5} y1={cy} x2={cx + r + 5} y2={cy} stroke={color + '22'} strokeWidth="0.8" />
      {/* Ticks */}
      {ticks.map((t, i) => (
        <line
          key={i}
          x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2}
          stroke={color + (t.isMajor ? '70' : '38')}
          strokeWidth={t.isMajor ? 1.4 : 0.8}
        />
      ))}
      {/* Needle — wrapped in translate group so rotation origin = pivot (0,0 in group coords) */}
      <g transform={`translate(${cx}, ${cy})`}>
        <line
          x1={0} y1={0} x2={0} y2={-(r - 7)}
          stroke={color} strokeWidth="1.8" strokeLinecap="round"
          style={{
            transformBox: 'fill-box',
            transformOrigin: '50% 100%',
            animation: 'gaugeNeedle 4s ease-in-out infinite',
          }}
        />
      </g>
      {/* Pivot dot */}
      <circle cx={cx} cy={cy} r="3.5" fill={color} fillOpacity="0.80" />
    </svg>
  )
}

// ─── Rendering Overlay ───────────────────────────────────────────────────────

function RenderingOverlay({ mode }: { mode: string }) {
  const info = getModeInfo(mode)
  return (
    <div
      className="absolute inset-0 z-20 rounded-lg overflow-hidden flex items-center justify-center"
      style={{ backgroundColor: '#19120C' }}
    >
      {/* TV grain */}
      <NoiseCanvas />

      {/* CRT scanlines */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.18) 0px, rgba(0,0,0,0.18) 1px, transparent 1px, transparent 3px)',
          zIndex: 1,
        }}
      />

      {/* Analog sweep band */}
      <div
        className="absolute left-0 right-0 pointer-events-none"
        style={{
          height: '80px',
          background: 'linear-gradient(to bottom, transparent, rgba(232,202,162,0.06) 30%, rgba(232,202,162,0.13) 50%, rgba(232,202,162,0.06) 70%, transparent)',
          top: '-80px',
          animation: 'scanSweep 3.2s linear infinite',
          zIndex: 2,
        }}
      />

      {/* Content */}
      <div className="relative flex flex-col items-center gap-1" style={{ zIndex: 3 }}>
        <div
          className="font-title animate-flicker select-none"
          style={{
            fontSize: '3.2rem',
            lineHeight: 1.1,
            color: '#EDE3D0',
            textShadow: `0 0 24px ${info.color}55, 0 0 60px ${info.color}22`,
          }}
        >
          {info.label}
        </div>
        <TuningGauge color={info.color} />
        <div
          className="font-display text-[11px] tracking-[0.35em]"
          style={{ color: `${info.color}85`, marginTop: '-2px' }}
        >
          Tuning
        </div>
      </div>

      {/* Vignette */}
      <div
        className="absolute inset-0 pointer-events-none rounded-lg"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(10,7,4,0.65) 100%)',
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
    <div className="relative w-full bg-deep rounded-lg overflow-hidden" style={{ aspectRatio: '5/3', border: '1px solid rgba(74,75,89,0.12)' }}>
      <div className="absolute inset-[6px] border border-border-default/40 rounded pointer-events-none z-10" />

      {waiting && <RenderingOverlay mode={waitingMode} />}

      {!waiting && !loaded && !errored && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
          <div className="w-px h-8 bg-accent/30 animate-pulse-accent" />
          <span className="label tracking-[0.3em]">loading frame</span>
        </div>
      )}

      {!waiting && errored && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
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
      <div className="space-y-0.5">
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
                <div className="h-0.5 rounded-full mx-3 my-0.5" style={{ backgroundColor: '#CA796D', boxShadow: '0 0 6px rgba(202,121,109,0.5)' }} />
              )}
              <div
                draggable={!isComingSoon}
                onDragStart={e => handleDragStart(e, idx)}
                onDragOver={e => handleDragOver(e, idx)}
                onDrop={e => handleDrop(e, idx)}
                onDragEnd={handleDragEnd}
                className={cx(
                  'flex items-center gap-3 px-4 py-3 rounded-md transition-all duration-150',
                  isComingSoon
                    ? 'opacity-35'
                    : isEnabled
                      ? 'bg-surface hover:bg-surface-hover'
                      : 'bg-deep/50 opacity-60 hover:opacity-80',
                  isDragging ? 'opacity-40 scale-[0.98]' : '',
                )}
                style={{
                  border: isEnabled && !isComingSoon
                    ? `1px solid ${info.color}35`
                    : '1px solid rgba(74,75,89,0.10)',
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
                    border: isEnabled ? `1px solid ${info.color}` : '1px solid rgba(74,75,89,0.2)',
                    backgroundColor: isEnabled ? info.color : '#E8E0CA',
                  }}
                >
                  {isEnabled && (
                    <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                      <path d="M1 4l2.5 2.5L9 1" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>

                <span className="text-sm flex-shrink-0 w-5 text-center" style={{ color: isEnabled ? info.color : '#978A80' }}>
                  {info.icon}
                </span>
                <span
                  className={cx(
                    'font-title text-sm flex-1',
                    isComingSoon ? 'text-muted' : 'text-primary',
                  )}
                  style={{ color: isEnabled && !isComingSoon ? info.color : undefined }}
                >
                  {info.label}
                </span>

                {isCurrent && (
                  <span
                    className="font-display text-[9px] font-bold tracking-[0.1em] px-2 py-0.5 rounded-full"
                    style={{ color: info.color, backgroundColor: `${info.color}18` }}
                  >
                    NOW
                  </span>
                )}

                {isComingSoon && (
                  <span className="font-display text-[9px] font-bold uppercase tracking-[0.1em] text-muted px-2 py-0.5 rounded-full bg-elevated">
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
            className="w-16 bg-deep rounded-sm text-primary font-display text-sm px-2 py-1.5 outline-none transition-all duration-200 text-center"
            style={{ border: '1px solid rgba(74,75,89,0.15)' }}
            onFocus={e => (e.target.style.borderColor = '#CA796D')}
            onBlur={e => (e.target.style.borderColor = 'rgba(74,75,89,0.15)')}
          />
          <span className="label">min</span>
          <span className="label ml-auto" style={{ color: '#6B8FA0' }}>
            {enabledCount} modes · {interval * enabledCount} min cycle
          </span>
        </div>
      )}

      <div className="flex items-center gap-2 pt-1 flex-wrap">
        <button
          onClick={handleSave}
          disabled={saving}
          className="font-display text-xs font-bold uppercase tracking-widest px-5 py-2.5 rounded-sm bg-accent text-cream hover:bg-accent-hover transition-all duration-200 disabled:opacity-50 disabled:cursor-wait"
          style={{ boxShadow: '0 0 20px rgba(202,121,109,0.20)' }}
        >
          {saving ? 'Saving…' : 'Save playlist'}
        </button>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className={cx(
            'flex items-center gap-2 font-display text-xs font-bold uppercase tracking-widest',
            'px-4 py-2.5 rounded-sm transition-all duration-200 outline-none',
            refreshing
              ? 'bg-surface text-accent/50 cursor-wait'
              : 'bg-surface text-secondary hover:bg-surface-hover hover:text-accent cursor-pointer',
          )}
          style={{ border: '1px solid rgba(74,75,89,0.10)' }}
        >
          <RefreshIcon spinning={refreshing} />
          {refreshing ? 'Rendering…' : 'Force refresh'}
        </button>
        {saved && (
          <span className="label animate-fade-in" style={{ color: '#8DA495' }}>Saved</span>
        )}
      </div>
    </div>
  )
}

// ─── Stats Card ──────────────────────────────────────────────────────────────

function StatRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2" style={{ borderBottom: '1px solid rgba(74,75,89,0.08)' }}>
      <span className="label flex-shrink-0">{label}</span>
      <span className="value text-right truncate max-w-[140px]">{value}</span>
    </div>
  )
}

// ─── Status Grid ─────────────────────────────────────────────────────────────

function StatusRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5" style={{ borderBottom: '1px solid rgba(74,75,89,0.10)' }}>
      <span className="label flex-shrink-0">{label}</span>
      <span className="value text-right truncate max-w-[220px]">{value}</span>
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
          <div className="label mb-1">▶ On from</div>
          <input
            type="time"
            value={activeFrom}
            onChange={e => setActiveFrom(e.target.value)}
            className="w-full bg-deep rounded-sm text-primary font-display text-sm px-3 py-2 outline-none transition-all duration-200"
            style={{ border: '1px solid rgba(74,75,89,0.15)' }}
            onFocus={e => (e.target.style.borderColor = '#CA796D')}
            onBlur={e => (e.target.style.borderColor = 'rgba(74,75,89,0.15)')}
          />
        </div>
        <span className="label pb-2" style={{ color: '#CA796D' }}>→</span>
        <div>
          <div className="label mb-1">⏹ Off at</div>
          <input
            type="time"
            value={activeTo}
            onChange={e => setActiveTo(e.target.value)}
            className="w-full bg-deep rounded-sm text-primary font-display text-sm px-3 py-2 outline-none transition-all duration-200"
            style={{ border: '1px solid rgba(74,75,89,0.15)' }}
            onFocus={e => (e.target.style.borderColor = '#CA796D')}
            onBlur={e => (e.target.style.borderColor = 'rgba(74,75,89,0.15)')}
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
                'w-9 h-9 text-[12px] font-display font-bold rounded-sm transition-all duration-200 outline-none',
                days.includes(i)
                  ? 'bg-accent text-cream'
                  : 'bg-deep text-tertiary hover:text-primary cursor-pointer',
              )}
              style={{ border: days.includes(i) ? '1px solid #CA796D' : '1px solid rgba(74,75,89,0.15)' }}
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
          className="font-display text-xs font-bold uppercase tracking-widest px-5 py-2.5 rounded-sm bg-accent text-cream hover:bg-accent-hover transition-all duration-200 disabled:opacity-50 disabled:cursor-wait"
          style={{ boxShadow: '0 0 20px rgba(202,121,109,0.20)' }}
        >
          {mut.isPending ? 'Saving…' : 'Save schedule'}
        </button>
        {saved && (
          <span className="label animate-fade-in" style={{ color: '#8DA495' }}>Saved</span>
        )}
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
    <div className="flex items-center gap-3 py-2.5" style={{ borderBottom: '1px solid rgba(74,75,89,0.10)' }}>
      <span className="text-sm" style={{ color }}>{icon}</span>
      <span className="font-title text-sm flex-shrink-0 w-20" style={{ color }}>{modeName}</span>
      <input
        type="number"
        min={1}
        max={1440}
        value={minutes}
        onChange={e => setMinutes(Math.max(1, parseInt(e.target.value) || 1))}
        className="w-16 bg-deep rounded-sm text-primary font-display text-sm px-2 py-1.5 outline-none transition-all duration-200 text-center"
        style={{ border: '1px solid rgba(74,75,89,0.15)' }}
        onFocus={e => (e.target.style.borderColor = '#CA796D')}
        onBlur={e => (e.target.style.borderColor = 'rgba(74,75,89,0.15)')}
      />
      <span className="label">min</span>
      <button
        onClick={() => setMut.mutate()}
        disabled={setMut.isPending}
        className="font-display text-[11px] font-bold uppercase tracking-widest px-3 py-1.5 rounded-sm bg-surface text-secondary hover:bg-surface-hover hover:text-accent transition-all duration-200 disabled:opacity-50"
        style={{ border: '1px solid rgba(74,75,89,0.10)' }}
      >
        {setMut.isPending ? '…' : 'Set'}
      </button>
      {data.overridden && (
        <button
          onClick={() => resetMut.mutate()}
          disabled={resetMut.isPending}
          className="label hover:text-danger transition-colors"
          title={`Reset to default (${fmtInterval(data.default)})`}
          style={{ color: '#C05050' }}
        >
          reset
        </button>
      )}
      <span className="label ml-auto text-right">
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
          className="flex-1"
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
    </div>
  )
}

// ─── Weather Settings ────────────────────────────────────────────────────────

function WeatherSettings({ currentLocation }: { currentLocation?: string }) {
  const qc = useQueryClient()
  const [input, setInput] = useState(currentLocation ?? '')
  const [suggestions, setSuggestions] = useState<Array<{ name: string; display: string }>>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [saved, setSaved] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (currentLocation && !input) setInput(currentLocation)
  }, [currentLocation])

  const searchMut = useMutation({
    mutationFn: (q: string) => api.searchWeatherLocation(q),
    onSuccess: (data) => {
      setSuggestions(data.results)
      setShowSuggestions(data.results.length > 0)
    },
  })

  const saveMut = useMutation({
    mutationFn: () => api.setWeatherLocation(input),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['status'] })
      setSaved(true)
      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setSaved(false), 2500)
    },
  })

  const handleInputChange = (val: string) => {
    setInput(val)
    clearTimeout(debounceRef.current)
    if (val.length >= 2) {
      debounceRef.current = setTimeout(() => searchMut.mutate(val), 400)
    } else {
      setSuggestions([])
      setShowSuggestions(false)
    }
  }

  const selectSuggestion = (name: string) => {
    setInput(name)
    setSuggestions([])
    setShowSuggestions(false)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="label flex-shrink-0">Location</span>
        <div className="relative flex-1">
          <input
            type="text"
            value={input}
            onChange={e => handleInputChange(e.target.value)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="City name…"
            className="w-full bg-deep rounded-sm text-primary font-display text-sm px-3 py-2 outline-none transition-all duration-200"
            style={{ border: '1px solid rgba(74,75,89,0.15)' }}
            onFocus={e => { e.target.style.borderColor = '#CA796D' }}
          />
          {showSuggestions && suggestions.length > 0 && (
            <div
              className="absolute top-full left-0 right-0 mt-1 bg-surface rounded-sm z-50 overflow-hidden"
              style={{ border: '1px solid rgba(74,75,89,0.15)' }}
            >
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => selectSuggestion(s.name)}
                  className="w-full text-left px-3 py-2 font-display text-sm text-secondary hover:bg-surface-hover hover:text-accent transition-colors"
                >
                  <span className="text-primary">{s.name}</span>
                  <span className="text-muted text-xs ml-2">{s.display.slice(0, 55)}…</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending || !input.trim()}
          className="font-display text-xs font-bold uppercase tracking-widest px-5 py-2.5 rounded-sm bg-accent text-cream hover:bg-accent-hover transition-all duration-200 disabled:opacity-50"
          style={{ boxShadow: '0 0 20px rgba(202,121,109,0.20)' }}
        >
          {saveMut.isPending ? 'Saving…' : 'Set location'}
        </button>
        {saved && <span className="label animate-fade-in" style={{ color: '#8DA495' }}>Saved</span>}
      </div>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const clock = useClock()
  const qc = useQueryClient()
  const [refreshKey, setRefreshKey] = useState(Date.now())
  const [waitingSince, setWaitingSince] = useState<number | null>(null)
  const [pendingMode, setPendingMode] = useState<string | null>(null)
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

  // Clear pending mode when overlay disappears
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

  return (
    <div className="min-h-screen bg-bg text-primary font-display animate-fade-in">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 backdrop-blur-sm" style={{ backgroundColor: 'rgba(241,235,217,0.93)', borderBottom: '1px solid rgba(74,75,89,0.10)' }}>
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="w-2.5 h-2.5 rounded-full bg-accent" style={{ boxShadow: '0 0 12px rgba(202,121,109,0.4)' }} />
            <div className="flex flex-col gap-0">
              <span className="font-title text-xl leading-tight" style={{ color: '#3B3C47' }}>TaleVision</span>
              <span className="font-display text-[12px] text-tertiary italic leading-tight">
                {TAGLINE}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-5">
            <span className="font-display text-sm text-tertiary tabular-nums">{clock}</span>
            <div className="flex items-center gap-2">
              <span
                className={cx(
                  'w-2 h-2 rounded-full',
                  isError ? 'bg-danger animate-pulse' :
                  isSuspended ? 'bg-tertiary' :
                  'bg-success',
                )}
                style={{
                  boxShadow: isError ? '0 0 8px rgba(192,80,80,0.4)' :
                             !isSuspended && !isError ? '0 0 8px rgba(141,164,149,0.5)' : undefined,
                }}
              />
              <span
                className="label"
                style={{
                  color: isError ? '#C05050' :
                         isSuspended ? '#7C706A' :
                         currentModeInfo.color,
                }}
              >
                {isError ? 'offline' :
                 isSuspended ? '⏸ suspended' :
                 isRotating
                   ? `${currentModeInfo.icon} ${currentMode} · ${playlist.length} in rotation`
                   : `${currentModeInfo.icon} ${currentMode}`}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Main content ───────────────────────────────────────────────── */}
      <main className="max-w-4xl mx-auto px-6 py-8 space-y-8">

        {/* Frame Preview */}
        <section>
          <FramePreview refreshKey={refreshKey} waiting={waiting} waitingMode={pendingMode ?? currentMode} />
        </section>

        {/* Language — always visible, top priority */}
        <section className="bg-surface rounded-lg p-5" style={{ border: '1px solid rgba(74,75,89,0.10)' }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-title text-base text-primary">Language</h2>
            <span className="label" style={{ color: '#6B8FA0' }}>LitClock + Wikipedia</span>
          </div>
          <LanguageSelector current={status?.language ?? undefined} />
        </section>

        {/* Playlist + Stats — two column */}
        <section className="flex items-start gap-6">
          <div className="flex-1 min-w-0">
            <h2 className="font-title text-base text-primary mb-3">Playlist</h2>
            <PlaylistEditor
              playlist={playlist}
              rotationInterval={rotationInterval}
              currentMode={currentMode}
              onSave={(modes, interval) => playlistMut.mutate({ modes, interval })}
              saving={playlistMut.isPending}
              onRefresh={handleRefresh}
              refreshing={refreshMut.isPending}
            />
          </div>

          {/* Stats */}
          <div className="w-52 flex-shrink-0">
            <h2 className="font-title text-base text-primary mb-3">Stats</h2>
            <div className="bg-surface rounded-lg p-4" style={{ border: '1px solid rgba(74,75,89,0.10)' }}>
              <StatRow label="Uptime" value={formatUptime(status?.uptime_seconds ?? 0)} />
              <StatRow label="Last render" value={formatLastRender(status?.last_update)} />
              {status?.next_wake && (
                <StatRow label="Next wake" value={formatTime(status.next_wake)} />
              )}
              <StatRow
                label="Mode"
                value={
                  <span className="font-title text-sm" style={{ color: currentModeInfo.color }}>
                    {currentModeInfo.icon} {currentMode}
                  </span>
                }
              />
              {isRotating && (
                <StatRow
                  label="Rotation"
                  value={<span style={{ color: '#6B8FA0' }}>{fmtInterval(rotationInterval)}</span>}
                />
              )}
              <StatRow
                label="Status"
                value={
                  <span style={{ color: isSuspended ? '#C8974A' : '#8DA495' }}>
                    {isSuspended ? '⏸ paused' : '▶ active'}
                  </span>
                }
              />
            </div>
          </div>
        </section>

        <div style={{ borderTop: '1px solid rgba(74,75,89,0.10)' }} />

        {/* Status + Suspend — two-column grid */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-8">

          {/* Status */}
          <div className="bg-surface rounded-lg p-5" style={{ border: '1px solid rgba(74,75,89,0.10)' }}>
            <h2 className="font-title text-base text-primary mb-4">Status</h2>
            <div>
              <StatusRow
                label="Mode"
                value={
                  <span className="font-title text-base font-semibold" style={{ color: currentModeInfo.color }}>
                    {currentModeInfo.icon} {currentMode}
                  </span>
                }
              />
              {isRotating && (
                <StatusRow
                  label="Rotation"
                  value={
                    <span style={{ color: '#6B8FA0' }}>
                      {playlist.map(id => getModeInfo(id).icon).join(' → ')} · {fmtInterval(rotationInterval)}
                    </span>
                  }
                />
              )}
              <StatusRow
                label="Suspended"
                value={
                  <span style={{ color: isSuspended ? '#C8974A' : '#8DA495' }}>
                    {isSuspended ? '⏸ yes' : '▶ no'}
                  </span>
                }
              />
              <StatusRow
                label="Last render"
                value={formatLastRender(status?.last_update)}
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
                  value={<span className="font-display text-base font-semibold" style={{ color: '#C8974A' }}>{status.video}</span>}
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
          <div className="bg-surface rounded-lg p-5" style={{ border: '1px solid rgba(74,75,89,0.10)' }}>
            <h2 className="font-title text-base text-primary mb-4">Active schedule</h2>
            <SuspendForm initial={status?.suspend} />
          </div>

        </section>

        {/* Refresh intervals — only in single mode */}
        {!isRotating && status?.intervals && Object.keys(status.intervals).length > 0 && (
          <section className="bg-surface rounded-lg p-5" style={{ border: '1px solid rgba(74,75,89,0.10)' }}>
            <h2 className="font-title text-base text-primary mb-4">Refresh intervals</h2>
            <div>
              {ALL_MODES.filter(m => m.available && status.intervals![m.id]).map(m => (
                <IntervalRow
                  key={m.id}
                  modeName={m.id}
                  data={status.intervals![m.id]}
                  color={m.color}
                  icon={m.icon}
                />
              ))}
            </div>
          </section>
        )}

        {/* Weather location — only for weather mode */}
        {currentMode === 'weather' && (
          <section className="animate-fade-in bg-surface rounded-lg p-5" style={{ border: '1px solid rgba(74,75,89,0.10)' }}>
            <h2 className="font-title text-base text-primary mb-3">Weather location</h2>
            <WeatherSettings currentLocation={status?.weather_location ?? undefined} />
          </section>
        )}

        {/* Footer */}
        <footer className="pt-8 pb-4 flex flex-col items-center gap-4">
          <div style={{ borderTop: '1px solid rgba(74,75,89,0.10)', width: '100%' }} />
          <div className="flex items-center justify-between w-full pt-4">
            <span className="label">TaleVision · Pi Zero W · 800 × 480 · e‑ink</span>
            <a
              href="https://github.com/enuzzo/talevision"
              target="_blank"
              rel="noopener noreferrer"
              className="label hover:text-accent transition-colors duration-200"
            >
              github ↗
            </a>
          </div>
          <div className="flex flex-col items-center gap-2 pt-6">
            <img
              src="https://netmi.lk/wp-content/uploads/2024/10/netmilk.svg"
              alt="Netmilk Studio"
              className="hover:animate-shake cursor-pointer"
              style={{ width: '130px', height: 'auto' }}
            />
            <span className="font-display text-[10px] text-muted text-center leading-relaxed">
              MIT License · enuzzo + Netmilk Studio · 2024
            </span>
          </div>
        </footer>

      </main>
    </div>
  )
}
