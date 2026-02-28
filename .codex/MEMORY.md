# TaleVision — Codex Private Memory

Stable public knowledge lives in `knowledge/PROJECT_KNOWLEDGE.md` (versioned).
This file contains only private/local context that must NOT be committed publicly.

## Prime Directives

- Never write secrets in plain text anywhere (files, logs, commits, this file)
- Preserve visual output: LitClock typography + SlowMovie QR+overlay are non-negotiable
- Pi Zero lean: no headless browsers, no heavy deps; PIL + Flask + inky only
- `archive/` is reference only — never modify, always gitignored

## Private Local Context

- Entry point: `python main.py`; config: `config.yaml`; secrets: `secrets.yaml` (local only)
- Dev sim output: `talevision_frame.png` — inspect visually to verify typography
- Pi hardware at the office — testable from Monday onwards
- `archive/` reference implementations: local only, gitignored, read-only

## Preflight Checklist (pre-push)

- [ ] `archive/` is in .gitignore and not tracked (`git status` confirms)
- [ ] `secrets.yaml` is in .gitignore and not tracked
- [ ] `media/*.mp4` files are in .gitignore
- [ ] No hardcoded passwords/tokens in any committed file
- [ ] `bandit -r talevision/ -ll` → 0 HIGH/MEDIUM findings
- [ ] `pip-audit -r requirements.txt` → 0 known CVEs
- [ ] `grep -rn "password=\|api_key=\|token=\|ssid=\|Authorization:" talevision/ config.yaml`
