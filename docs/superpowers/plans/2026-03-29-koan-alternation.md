# Koan Haiku/Paradox Alternation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alternate Koan mode output between 3-line haiku and single-line paradoxical Zen koan questions, with archive filtering.

**Architecture:** A render counter (persisted in the archive count) drives strict alternation: even = haiku, odd = koan. The generator gains a parallel `generate_koan()` function with a koan-specific system prompt. The renderer branches on type for layout (koan uses larger centered text, no pen name). Archive JSON gains a `"type"` field. Frontend adds a filter toggle.

**Tech Stack:** Python (PIL, urllib), React/TypeScript (Vite), existing Groq/Gemini LLM backends.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `talevision/modes/koan_generator.py` | Modify | Add `_koan_system_prompt()`, `generate_koan()`, `_parse_koan_output()` |
| `talevision/modes/koan_archive.py` | Modify | Add `type` field to `append()` |
| `talevision/modes/koan.py` | Modify | Alternation logic in `render()`, koan layout in `_draw_koan_frame()` |
| `talevision/web/api.py` | Modify | Add `?type=` query param filter to `/api/koan/archive` |
| `frontend/src/App.tsx` | Modify | Filter toggle (All/Haiku/Koan) in archive page, koan card variant |
| `tests/test_koan.py` | Modify | Tests for koan parser, alternation logic |

---

### Task 1: Koan Generator — `generate_koan()` + parser

**Files:**
- Modify: `talevision/modes/koan_generator.py`
- Modify: `tests/test_koan.py`

- [ ] **Step 1: Write failing tests for koan output parser**

Add to `tests/test_koan.py`:

```python
from talevision.modes.koan_generator import _parse_koan_output


def test_koan_clean_output():
    raw = "If silence has a shape, why does it shatter when named?"
    r = _parse_koan_output(raw, 800)
    assert r is not None
    assert r["line"] == "If silence has a shape, why does it shatter when named?"
    assert r["generation_time_ms"] == 800


def test_koan_strips_preamble():
    raw = "Here is a Zen koan:\n\nIf silence has a shape, why does it shatter when named?"
    r = _parse_koan_output(raw, 800)
    assert r is not None
    assert r["line"].startswith("If silence")


def test_koan_strips_quotes():
    raw = '"If silence has a shape, why does it shatter when named?"'
    r = _parse_koan_output(raw, 800)
    assert r is not None
    assert not r["line"].startswith('"')


def test_koan_empty_returns_none():
    r = _parse_koan_output("", 800)
    assert r is None


def test_koan_strips_chatml():
    raw = "<|im_start|>assistant\nIf silence has a shape, why does it shatter when named?<|im_end|>"
    r = _parse_koan_output(raw, 800)
    assert r is not None
    assert r["line"].startswith("If silence")


def test_koan_picks_longest_line():
    raw = "Sure, here you go:\n\nIf silence has a shape, why does it shatter when named?\n\nI hope you enjoy."
    r = _parse_koan_output(raw, 800)
    assert r is not None
    assert "silence" in r["line"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/enuzzo/Library/CloudStorage/Dropbox/Mitnick/TaleVision && python3 -m pytest tests/test_koan.py -v -k koan`
Expected: ImportError — `_parse_koan_output` does not exist.

- [ ] **Step 3: Implement `_koan_system_prompt()`, `generate_koan()`, `_parse_koan_output()`**

Add to `talevision/modes/koan_generator.py`:

```python
def _koan_system_prompt(lang: str = "en") -> str:
    lang_name = _LANG_NAMES.get(lang, "English")
    base = (
        "You are a Zen master living inside a tiny $5 computer "
        "mounted on a wall. You write paradoxical koan questions "
        f"in {lang_name}. Your koans are single questions with no answer — "
        "they reveal the absurdity, beauty, or impossibility hidden "
        "in everyday things. They sound like ancient Zen riddles "
        "but about modern or unexpected themes.\n\n"
    )
    if lang != "en":
        base += (
            f"IMPORTANT: Write DIRECTLY in {lang_name} as a native philosopher would — "
            "do NOT translate from English. Choose words for their paradoxical weight "
            "and poetic resonance in the target language.\n\n"
        )
    base += (
        "Output ONLY the koan question, nothing else. One single question. "
        "No preamble, no explanation, no attribution."
    )
    return base


def generate_koan(
    api_key: str,
    backend: str,
    seed_word: str,
    prompt_question: str = "",
    language: str = "en",
    timeout: int = 30,
) -> Optional[dict]:
    if not api_key:
        log.warning("Koan: no API key configured")
        return None

    user_msg = f"Theme: {seed_word}"
    if prompt_question:
        user_msg += f"\n{prompt_question}"
    user_msg += "\nWrite a single paradoxical koan question about this."

    log.info("Koan %s: generating koan (seed=%s, lang=%s)", backend, seed_word, language)
    t0 = time.monotonic()
    sys_prompt = _koan_system_prompt(language)

    try:
        if backend == "groq":
            resp = _call_groq(api_key, user_msg, timeout, lang=language,
                              system_prompt=sys_prompt)
        else:
            resp = _call_gemini(api_key, user_msg, timeout, lang=language,
                                system_prompt=sys_prompt)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.info("Koan %s: koan response in %dms, raw: %s",
                 backend, elapsed_ms, resp["raw"][:200])
        result = _parse_koan_output(resp["raw"], elapsed_ms)
        if result:
            result["model"] = resp["model"]
            result["prompt_tokens"] = resp["prompt_tokens"]
            result["completion_tokens"] = resp["completion_tokens"]
            result["total_tokens"] = resp["total_tokens"]
        return result

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        log.error("Koan %s HTTP error %d: %s", backend, exc.code, body)
        return None
    except Exception as exc:
        log.error("Koan %s error: %s", backend, exc)
        return None


def _parse_koan_output(raw: str, elapsed_ms: int) -> Optional[dict]:
    """Parse LLM output into a single koan question line."""
    raw = re.sub(r'<\|im_\w+\|>', '', raw).strip()
    if not raw:
        return None

    lines = [l.strip() for l in raw.split("\n") if l.strip()]
    # Pick the longest line (skip preamble / trailing filler)
    best = max(lines, key=len)
    # Strip surrounding quotes
    if best.startswith('"') and best.endswith('"'):
        best = best[1:-1].strip()
    if best.startswith('\u201c') and best.endswith('\u201d'):
        best = best[1:-1].strip()

    if not best:
        return None

    if not best.endswith("?"):
        log.warning("Koan: output does not end with '?' — may not be a question: %s", best[:80])

    return {
        "line": best,
        "generation_time_ms": elapsed_ms,
    }
```

**Also modify `_call_groq` and `_call_gemini`** to accept an optional `system_prompt` parameter and increase `max_tokens` for koan:

`_call_groq` (line 68): add `system_prompt: str = ""`, `max_tokens: int = 60` params. Use `sys_prompt = system_prompt or _system_prompt(lang)` in payload. Use `max_tokens` param in payload instead of hardcoded 60.

`_call_gemini` (line 101): same — add `system_prompt: str = ""`, `max_tokens: int = 60` params. Use `sys_prompt = system_prompt or _system_prompt(lang)` in `system_instruction`. Use `max_tokens` param as `maxOutputTokens`.

In `generate_koan()`, pass `system_prompt=sys_prompt` and `max_tokens=100` (koan questions need more tokens than haiku).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/enuzzo/Library/CloudStorage/Dropbox/Mitnick/TaleVision && python3 -m pytest tests/test_koan.py -v`
Expected: All tests PASS (both old haiku + new koan tests).

- [ ] **Step 5: Commit**

```bash
git add talevision/modes/koan_generator.py tests/test_koan.py
git commit -m "feat(koan): add generate_koan() and koan output parser"
```

---

### Task 2: Archive — add `type` field

**Files:**
- Modify: `talevision/modes/koan_archive.py`

- [ ] **Step 1: Add `type` parameter to `append()` method**

In `koan_archive.py`, modify `append()` signature to accept `entry_type: str = "haiku"` and include it in the JSON entry:

```python
def append(self, lines: list, seed_word: str, author_name: str,
           source: str = "generated", generation_time_ms: int = 0,
           model: str = "", prompt_tokens: int = 0,
           completion_tokens: int = 0, total_tokens: int = 0,
           entry_type: str = "haiku") -> int:
    # ... existing code ...
    entry = {
        "id": new_id,
        "type": entry_type,       # <-- ADD THIS
        "timestamp": ts.isoformat(),
        "lines": lines,
        # ... rest unchanged
    }
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `cd /Users/enuzzo/Library/CloudStorage/Dropbox/Mitnick/TaleVision && python3 -m pytest tests/test_koan.py -v`
Expected: All tests PASS (new param has default, backward compatible).

- [ ] **Step 3: Commit**

```bash
git add talevision/modes/koan_archive.py
git commit -m "feat(koan): add type field to archive entries"
```

---

### Task 3: KoanMode — alternation logic + koan layout

**Files:**
- Modify: `talevision/modes/koan.py`

- [ ] **Step 1: Add koan font and import**

At top of `koan.py`, update import:
```python
from talevision.modes.koan_generator import generate_haiku, generate_koan, get_random_prompt
```

In `__init__`, add a larger font for koan questions:
```python
self._font_koan = _load_font(fonts_dir / "CrimsonText-Regular.ttf", 38)
```

- [ ] **Step 2: Modify `render()` for strict alternation**

Replace the `render()` method. Alternation uses archive count: even = haiku, odd = koan.

```python
def render(self) -> Image.Image:
    w, h = self._display.width, self._display.height

    seed_word = self._archive.get_random_seed_word()
    prompt_q = get_random_prompt()

    # Strict alternation: even count = haiku, odd = koan
    current_count = self._archive.count()
    is_koan = (current_count % 2) == 1

    if is_koan:
        result = generate_koan(
            api_key=self._api_key,
            backend=self._backend,
            seed_word=seed_word,
            prompt_question=prompt_q,
            language=self._language,
        )
        # Fallback to haiku if koan generation fails (avoids infinite koan-retry loop)
        if not result:
            log.warning("Koan: koan generation failed, falling back to haiku")
            is_koan = False
            result = generate_haiku(
                api_key=self._api_key,
                backend=self._backend,
                seed_word=seed_word,
                prompt_question=prompt_q,
                language=self._language,
            )
    else:
        result = generate_haiku(
            api_key=self._api_key,
            backend=self._backend,
            seed_word=seed_word,
            prompt_question=prompt_q,
            language=self._language,
        )

    if result and is_koan:
        entry_id = self._archive.append(
            lines=[result["line"]],
            seed_word=seed_word,
            author_name="",
            source=self._backend,
            generation_time_ms=result["generation_time_ms"],
            model=result.get("model", ""),
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
            total_tokens=result.get("total_tokens", 0),
            entry_type="koan",
        )
        entry = {
            "id": entry_id,
            "type": "koan",
            "lines": [result["line"]],
            "seed_word": seed_word,
            "author_name": "",
            "source": self._backend,
            "generation_time_ms": result["generation_time_ms"],
            "model": result.get("model", ""),
            "total_tokens": result.get("total_tokens", 0),
        }
        self._last_haiku = entry
        log.info("Koan: fresh koan #%d (seed=%s)", entry_id, seed_word)
        return self._draw_koan_frame(w, h, entry)

    elif result:
        haiku_id = self._archive.append(
            lines=result["lines"],
            seed_word=seed_word,
            author_name=result["author_name"],
            source=self._backend,
            generation_time_ms=result["generation_time_ms"],
            model=result.get("model", ""),
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
            total_tokens=result.get("total_tokens", 0),
            entry_type="haiku",
        )
        haiku = {
            "id": haiku_id,
            "type": "haiku",
            "lines": result["lines"],
            "seed_word": seed_word,
            "author_name": result["author_name"],
            "source": self._backend,
            "generation_time_ms": result["generation_time_ms"],
            "model": result.get("model", ""),
            "total_tokens": result.get("total_tokens", 0),
        }
        self._last_haiku = haiku
        log.info("Koan: fresh haiku #%d (seed=%s, %.1fs)",
                 haiku_id, seed_word, result["generation_time_ms"] / 1000.0)
        return self._draw_frame(w, h, haiku)

    log.warning("Koan: generation failed, showing error frame")
    return self._error_image(w, h)
```

- [ ] **Step 2b: Update `_error_image()` text**

Change `koan.py` line 218 from `{self._archive.count()} haiku in archive` to `{self._archive.count()} entries in archive`.

- [ ] **Step 3: Add `_draw_koan_frame()` method**

Add after `_draw_frame()`:

```python
def _draw_koan_frame(self, w: int, h: int, entry: dict) -> Image.Image:
    """Render a paradoxical koan question — centered, larger font, no pen name."""
    if self._bg_image:
        img = ImageOps.fit(self._bg_image.copy(), (w, h), Image.LANCZOS)
    else:
        img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    RIGHT_EDGE = w - 50
    TOP_MARGIN = 40
    FILL = (80, 80, 80)
    KOAN_FILL = (30, 30, 30)

    koan_id = entry.get("id", 0)
    seed_word = entry.get("seed_word", "")
    koan_line = entry["lines"][0] if entry.get("lines") else ""

    # --- Theme + №: top-right ---
    header_text = f"{seed_word} · № {koan_id}"
    hw = draw.textbbox((0, 0), header_text, font=self._font_mono)[2]
    draw.text((RIGHT_EDGE - hw, TOP_MARGIN), header_text,
              font=self._font_mono, fill=FILL)

    # --- Koan: word-wrapped, right-aligned, optical center ---
    max_text_w = w - 140
    words = koan_line.split()
    wrapped_lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        tw = draw.textbbox((0, 0), test, font=self._font_koan)[2]
        if tw > max_text_w and current:
            wrapped_lines.append(current)
            current = word
        else:
            current = test
    if current:
        wrapped_lines.append(current)

    line_spacing = 48
    total_h = len(wrapped_lines) * line_spacing
    optical_y = int(h * 0.38)
    top_y = optical_y - total_h // 2

    for i, line in enumerate(wrapped_lines):
        lw = draw.textbbox((0, 0), line, font=self._font_koan)[2]
        draw.text((RIGHT_EDGE - lw, top_y + i * line_spacing), line,
                  font=self._font_koan, fill=KOAN_FILL)

    # --- Tech stats: bottom-right (no pen name for koan) ---
    gen_ms = entry.get("generation_time_ms", 0)
    model = entry.get("model", "")
    if gen_ms > 0 and model:
        gen_s = gen_ms / 1000.0
        model_short = model.split("/")[-1]
        tokens = entry.get("total_tokens", 0)
        tech_text = f"{model_short} · {gen_s:.1f}s · {tokens}tok"
    else:
        tech_text = f"seed:{seed_word}"
    tw = draw.textbbox((0, 0), tech_text, font=self._font_tech)[2]
    draw.text((RIGHT_EDGE - tw, h - 60), tech_text,
              font=self._font_tech, fill=FILL)

    return img
```

- [ ] **Step 4: Smoke test with --render-only**

Run: `cd /Users/enuzzo/Library/CloudStorage/Dropbox/Mitnick/TaleVision && python3 main.py --render-only --mode koan`
Expected: renders a PNG without crashing. Open and visually inspect.

- [ ] **Step 5: Commit**

```bash
git add talevision/modes/koan.py
git commit -m "feat(koan): alternate haiku/koan with dedicated koan layout"
```

---

### Task 4: API — archive filter by type

**Files:**
- Modify: `talevision/web/api.py:264-278`

- [ ] **Step 1: Add `?type=` query param to `/api/koan/archive`**

Replace the `koan_archive()` function:

```python
@api_bp.get("/koan/archive")
def koan_archive():
    """GET /api/koan/archive — list all generated haiku/koan. ?type=haiku|koan|all"""
    koan = _orchestrator()._modes.get("koan")
    if not koan:
        return jsonify({"haiku": [], "count": 0})
    archive = koan._archive
    files = archive._list_files()
    type_filter = request.args.get("type", "all")
    items = []
    for fp in reversed(files):
        entry = archive._load_file(fp)
        if entry:
            if type_filter != "all" and entry.get("type", "haiku") != type_filter:
                continue
            items.append(entry)
    return jsonify({"haiku": items, "count": len(items)})
```

- [ ] **Step 2: Verify manually**

Run on Pi after deploy, or just read the code — the filter is trivial.

- [ ] **Step 3: Commit**

```bash
git add talevision/web/api.py
git commit -m "feat(koan): add ?type= filter to archive API"
```

---

### Task 5: Frontend — filter toggle + koan card variant

**Files:**
- Modify: `frontend/src/App.tsx:842-1098`

- [ ] **Step 1: Add `type` to `KoanHaiku` interface**

```typescript
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
  type?: 'haiku' | 'koan'   // <-- ADD
}
```

- [ ] **Step 2: Add filter state and toggle to `KoanArchivePage`**

Inside `KoanArchivePage`, add state:
```typescript
const [typeFilter, setTypeFilter] = useState<'all' | 'haiku' | 'koan'>('all')
```

Add the filter toggle UI after the search input inside the header `<div className="mt-3">`:

```tsx
<div className="flex items-center gap-2 mt-2">
  {(['all', 'haiku', 'koan'] as const).map(t => (
    <button
      key={t}
      onClick={() => { setTypeFilter(t); setVisibleCount(30) }}
      className="font-mono text-xs px-3 py-1 rounded-full transition-all duration-200"
      style={{
        background: typeFilter === t ? '#FF1DA5' : 'rgba(0,0,0,0.04)',
        color: typeFilter === t ? '#FFFFFF' : '#A09890',
        fontWeight: typeFilter === t ? 700 : 400,
      }}
    >
      {t}
    </button>
  ))}
</div>
```

Update the `filtered` variable to also apply typeFilter:
```typescript
const typeFiltered = typeFilter === 'all'
  ? allHaiku
  : allHaiku.filter(h => (h.type ?? 'haiku') === typeFilter)

const filtered = search.trim()
  ? typeFiltered.filter(h =>
      h.seed_word.toLowerCase().includes(search.toLowerCase()) ||
      h.author_name.toLowerCase().includes(search.toLowerCase()) ||
      h.lines.some(l => l.toLowerCase().includes(search.toLowerCase()))
    )
  : typeFiltered
```

- [ ] **Step 3: Update `HaikuCard` to handle koan variant**

Modify the haiku lines section and pen name to handle koan type:

```tsx
{/* Haiku/Koan lines */}
<div
  className="leading-relaxed mb-3"
  style={{
    fontFamily: 'Georgia, "Crimson Text", "Times New Roman", serif',
    fontStyle: 'italic',
    fontSize: (h.type ?? 'haiku') === 'koan' ? '16px' : '14px',
    lineHeight: '1.8',
    color: '#2A2A3E',
  }}
>
  {h.lines.map((line, i) => (
    <div key={i}>{line}</div>
  ))}
</div>

{/* Pen name — only for haiku */}
{(h.type ?? 'haiku') === 'haiku' && h.author_name && (
  <div className="font-mono text-xs mb-3" style={{ color: '#FF1DA5' }}>
    — {h.author_name}
  </div>
)}
```

- [ ] **Step 4: Update `KoanArchivePanel` sidebar for koan entries**

Change the button text from `{count} haiku — view all →` to:
```tsx
{count} entries — view all →
```

Wrap the pen name line (line 901) in a conditional so empty author_name doesn't render `— `:
```tsx
{latest.author_name && (
  <div className="mt-2 font-mono text-xs text-muted/80">— {latest.author_name}</div>
)}
```

Update the footer text:
```tsx
TaleVision · Koan · {count} entries preserved
```

Update empty-state text in `KoanArchivePage` (lines 990-991) from `'no haiku match your search'` / `'no haiku yet'` to `'no entries match your search'` / `'no entries yet'`.

- [ ] **Step 5: Build frontend**

Run: `cd /Users/enuzzo/Library/CloudStorage/Dropbox/Mitnick/TaleVision/frontend && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(koan): add haiku/koan filter toggle to archive page"
```

---

### Task 6: Flora — verify + commit pending changes

**Files:**
- Modified (unstaged): `talevision/modes/flora.py`

- [ ] **Step 1: Smoke test Flora**

Run: `cd /Users/enuzzo/Library/CloudStorage/Dropbox/Mitnick/TaleVision && python3 main.py --render-only --mode flora`
Expected: renders PNG without errors. Open and verify sidebar typography.

- [ ] **Step 2: Commit Flora changes**

```bash
git add talevision/modes/flora.py
git commit -m "fix(flora): refine sidebar typography and font sizes"
```

---

### Task 7: README — add Flora section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Flora section between Cucina and Playlist**

Insert after the Cucina section (after line 189 `---`):

```markdown
## Flora

Once per day: generate a unique botanical specimen from L-system grammars, seeded by today's date, and render it as a scientific illustration on the display.

Eight species rotate through the year — fern, tree, bush, vine, flower, bamboo, reed, and spring bulbs (Narcissus, Galanthus, Tulipa). Each produces a different branching structure via formal grammar rewriting. The daily seed ensures the same plant stays on the wall all day; tomorrow brings a different one. No API calls, no network, no tokens — the entire generation is deterministic and offline.

**Layout:** the display splits into a 500px white plant panel (left) and a 300px cream label card (right). The L-system plant grows upward from the bottom of the white panel, auto-scaled to fit. The label card shows the specimen number, genus (Lobster 38pt), species epithet (Taviraj Italic 24pt), family, order, observation date, and an optional location. Below the taxonomy: the L-system production rules in Inconsolata mono — the recipe that built the plant. A dark navy footer bar shows "FLORA", the seed date, species ID, and current time.

**Rendering:** turtle graphics on PIL. Tree-like species (tree, bush, vine) draw brown trunks that thin with depth — `_TRUNK_DARK` 5px at the base down to `_STEM_LIGHT` 1px at the tips. Non-tree species use green stems throughout. Every branch tip gets a leaf cluster (3 small ellipses in randomised greens). Flowering species add 4-petal flowers with yellow centres at branch tips, with species-specific colours and probabilities. Angular jitter (±2.5°) on every segment prevents the mechanical look that plagues most L-system renderers.

**Deterministic seed:** `random.Random(today.isoformat())` — same date, same plant. Specimen number: `date.toordinal() % 9999 + 1`.

**Archive:** each day's specimen is saved as `cache/flora_archive/YYYY-MM-DD.{json,png}`. Idempotent — re-renders on the same day don't duplicate. Automatic cap at `max_archive` entries (default 1000, ~2.7 years). Browsable via `/api/flora/archive`. The archive page uses a light Vibemilk theme with green accents, responsive grid, and click-to-enlarge lightbox.

**Refresh:** 3600 seconds (once per hour). Since the seed is date-based, every render in the same day produces the identical plant — the long interval just saves CPU on the Pi Zero.
```

- [ ] **Step 2: Add Flora to the Table of Contents**

Insert `- [Flora](#flora)` between Cucina and Playlist in the TOC.

- [ ] **Step 3: Update the intro paragraph**

Change "All seven modes" to "All eight modes" and add Flora to the screenshot grid in the gallery table.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add Flora section to README"
```

---

### Task 8: Final commit + push

- [ ] **Step 1: Run all tests**

Run: `cd /Users/enuzzo/Library/CloudStorage/Dropbox/Mitnick/TaleVision && python3 -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Push to remote**

```bash
git push origin main
```

- [ ] **Step 3: Update MEMORY.md with Koan alternation info**

Add koan alternation details to the Koan section of memory.
