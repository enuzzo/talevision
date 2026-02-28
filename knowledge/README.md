# Knowledge Base

Shared, provider-agnostic project knowledge for assistants and humans.

This folder is public and versioned by design.

## Why Public

- Makes context portable across assistants (Codex, Claude, Gemini, etc.).
- Keeps project practices visible to collaborators.
- Reduces lock-in to provider-specific memory systems.

## Canonical Files

- `README.md`: policy and structure for this folder.
- `ASSISTANT_BOOTSTRAP_PROMPT.md`: prompt to paste at session start.
- `PROJECT_KNOWLEDGE.md`: stable technical context and defaults.
- `DECISIONS.md`: concise architectural/operational decisions (ADR-lite).

## Data Policy (Mandatory)

Never store in `knowledge/`:

- secrets, tokens, passwords, API keys
- local machine paths (`/Users/...`, `C:\Users\...`)
- LAN/private infra details (IPs, hostnames, SSIDs, MACs)
- personal device identifiers (serial ports, USB IDs)
- raw terminal dumps with local/private metadata

Use placeholders:

- `<PROJECT_ROOT>`
- `<PORT>`
- `<DEVICE_IP>`
- `<WIFI_SSID>`
- `<API_KEY>`

## Writing Rules

- Keep content reusable, short, and verifiable.
- Move ephemeral debugging details to private local memory (not versioned).
- Update `PROJECT_KNOWLEDGE.md` only for stable facts.
- Append decisions to `DECISIONS.md` with date, context, choice, impact.
