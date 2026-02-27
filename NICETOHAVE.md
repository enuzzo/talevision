# TaleVision — Nice-to-Have Backlog

Items here are explicitly out of scope for the initial build but worth tracking.

## Onboarding
- Wi-Fi onboarding: AP/captive portal mode for unknown networks (hostapd + dnsmasq)
- First-run wizard: configure Wi-Fi, display type, default mode via web form

## Dashboard Enhancements
- Font selector (per-mode, applied without restart)
- Invert colors toggle (LitClock) from dashboard
- Per-mode advanced options panel
- Dark/light theme toggle for the dashboard itself
- Display last-rendered frame timestamp + age indicator

## Scheduling
- Per-day playlists (different modes/languages on different weekdays)
- Alternation between modes on a schedule (e.g. litclock 06:00–22:00, slowmovie 22:00–06:00)
- Grace period: don't suspend immediately, wait for current render to finish

## Testing
- Automated visual regression testing (render to file, compare PNG hashes)
- Unit tests for SuspendScheduler (overnight window edge cases)
- Unit tests for wrap_text_block() with long/multiline quotes

## Quality / Visuals
- Brightness auto-adjust by time of day (dim at night, bright in morning)
- Multiple language rotation (cycle through languages hourly)
- SlowMovie: playlist control (sequential, shuffle, single-loop)
- SlowMovie: manual frame seek from dashboard (slider)
- LitClock: per-minute history (last N quotes shown in dashboard)

## Infrastructure
- Optional HTTP basic auth on dashboard (bcrypt hash in secrets.yaml)
- Healthcheck endpoint `/api/health` for monitoring
- Prometheus metrics endpoint `/metrics`
- Auto-update via `git pull` from dashboard button
- Log viewer in dashboard (last N lines)
