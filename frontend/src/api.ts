import type { Status, SuspendConfig } from './types'

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() as Promise<T>
}

export const api = {
  status: () =>
    fetch('/api/status').then(r => json<Status>(r)),

  languages: () =>
    fetch('/api/languages').then(r => json<{ languages: string[] }>(r)),

  setMode: (mode: string) =>
    fetch('/api/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    }).then(r => json<{ ok: boolean }>(r)),

  refresh: () =>
    fetch('/api/refresh', { method: 'POST' }).then(r => json<{ ok: boolean }>(r)),

  setLanguage: (lang: string) =>
    fetch('/api/language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lang }),
    }).then(r => json<{ ok: boolean }>(r)),

  suspend: (data: SuspendConfig) =>
    fetch('/api/suspend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(r => json<{ ok: boolean }>(r)),

  setInterval: (mode: string, seconds: number) =>
    fetch('/api/interval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, seconds }),
    }).then(r => json<{ ok: boolean }>(r)),

  resetInterval: (mode: string) =>
    fetch(`/api/interval/${mode}`, { method: 'DELETE' }).then(r => json<{ ok: boolean }>(r)),
}
