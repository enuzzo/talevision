import { useEffect, useRef } from 'react'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  opacity: number
  opacityDelta: number
  color: string
}

const COLORS = [
  'rgba(117, 81, 255,',   // accent violet
  'rgba(57, 184, 255,',   // cyan
  'rgba(134, 140, 255,',  // soft violet
]

function makeParticle(w: number, h: number): Particle {
  const speed = 0.08 + Math.random() * 0.18
  const angle = -Math.PI / 2 + (Math.random() - 0.5) * 0.8  // mostly upward, slight drift
  return {
    x: Math.random() * w,
    y: Math.random() * h,
    vx: Math.cos(angle) * speed,
    vy: Math.sin(angle) * speed,
    r: 0.4 + Math.random() * 1.4,
    opacity: 0.05 + Math.random() * 0.2,
    opacityDelta: (Math.random() < 0.5 ? 1 : -1) * (0.0003 + Math.random() * 0.0006),
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
  }
}

export default function ParticleBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mouseRef = useRef({ x: -9999, y: -9999 })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    let particles: Particle[] = []

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
      particles = Array.from({ length: 80 }, () =>
        makeParticle(canvas.width, canvas.height)
      )
    }

    const onMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY }
    }
    const onMouseLeave = () => {
      mouseRef.current = { x: -9999, y: -9999 }
    }

    resize()
    window.addEventListener('resize', resize)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseleave', onMouseLeave)

    const tick = () => {
      const { width: w, height: h } = canvas
      ctx.clearRect(0, 0, w, h)

      const mx = mouseRef.current.x
      const my = mouseRef.current.y

      for (const p of particles) {
        p.x += p.vx
        p.y += p.vy
        p.opacity += p.opacityDelta

        // Mouse repulsion — gentle position nudge
        const dx = p.x - mx
        const dy = p.y - my
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 110 && dist > 0) {
          const strength = (110 - dist) / 110 * 0.35
          p.x += (dx / dist) * strength
          p.y += (dy / dist) * strength
        }

        // Clamp opacity and reverse direction at bounds
        if (p.opacity > 0.45 || p.opacity < 0.08) {
          p.opacityDelta *= -1
          p.opacity = Math.max(0.08, Math.min(0.45, p.opacity))
        }

        // Wrap around edges
        if (p.x < -4) p.x = w + 4
        if (p.x > w + 4) p.x = -4
        if (p.y < -4) p.y = h + 4
        if (p.y > h + 4) p.y = -4

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `${p.color}${p.opacity})`
        ctx.fill()
      }

      animId = requestAnimationFrame(tick)
    }

    tick()

    return () => {
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseleave', onMouseLeave)
      cancelAnimationFrame(animId)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{ zIndex: 0 }}
    />
  )
}
