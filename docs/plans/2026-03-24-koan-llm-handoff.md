# Koan Mode — Session Handoff Notes (2026-03-24)

## What Was Done This Session

### Museo
- Fixed AIC provider (Cloudflare 403 block on IIIF images) — disabled, code kept in `aic.py`
- Added V&A provider (Victoria and Albert Museum, London, 732k objects, no API key)
- Removed Harvard and Smithsonian (required registration)
- Final roster: Met (~200k) + Cleveland (~41k) + V&A (~732k) = ~973k artworks, zero keys
- Simplified `__init__.py` back to static `PROVIDERS` list (no factory function)

### Koan Visual Design (COMPLETE)
- Iterated layout ON the actual e-ink display via SSH + `inky.auto`
- Approved layout: bamboo ink wash bg, Crimson Text Regular 46pt haiku, right-aligned
- InconsolataNerdFontMono-Bold for seed №, pen name (uppercase), tech stats
- Tech stats line: model/seed/time — zen/nerd contrast
- All committed and deployed

### Koan LLM Infrastructure (BUILT, NEEDS TESTING)
- `llama.zero` cloned and compiled on Pi Zero W — binary at `~/llama.zero/build/bin/llama-cli` (1.5MB)
- SmolLM-135M-Instruct Q4_K_M downloaded — `~/models/smollm-135m-instruct-q4_k_m.gguf` (101MB)
- `koan_generator.py` written — subprocess call, prompt engineering, output parsing
- `koan.py` updated — `_generate()` calls generator, archives result, renders
- **NOT YET TESTED END-TO-END** — the generation command was running but this session got stuck monitoring SSH

## What Remains To Do

### 1. Test LLM generation on Pi (CRITICAL)
The first test command was launched but never completed in this session. To test:

```bash
# SSH to Pi
ssh enuzzo@talevision.local

# Kill any lingering llama-cli processes first
pkill llama-cli

# Test generation directly (should take ~2 minutes)
cd ~/llama.zero
./build/bin/llama-cli \
  -m ~/models/smollm-135m-instruct-q4_k_m.gguf \
  -p "<|im_start|>system
You are a contemplative poet living inside a small computer. You write haiku (5-7-5 syllables, 3 lines) in English. Your haiku are deeply introspective. After the haiku, sign with a short poetic pen name (2 words max). Output ONLY the haiku and signature.

Format:
line one
line two
line three
— Pen Name<|im_end|>
<|im_start|>user
Theme: silence
What do you feel in the silence between your thoughts?
Write a haiku about this.<|im_end|>
<|im_start|>assistant
" \
  -n 60 --temp 0.9 --top-p 0.95 --repeat-penalty 1.1 --log-disable -e
```

**IMPORTANT**: Do NOT try to monitor this from the Mac via SSH polling — that's what caused this session to get stuck. Either:
- SSH in manually and wait for the result
- Launch the command with `nohup` and redirect to a file, then check the file later
- Or just configure and restart talevision service and check the logs

### 2. Configure config.yaml on Pi
Add to `config.yaml` on the Pi:
```yaml
koan:
  refresh_interval: 600
  llm_binary: /home/enuzzo/llama.zero/build/bin/llama-cli
  llm_model: /home/enuzzo/models/smollm-135m-instruct-q4_k_m.gguf
  llm_timeout: 300
```

### 3. Deploy and verify
```bash
# On Mac
git push

# On Pi
cd ~/talevision && git pull
# Edit config.yaml with the llm paths above
sudo systemctl restart talevision
# Check logs
journalctl -u talevision -f
```

### 4. Potential issues to watch for
- **Memory**: llama-cli uses ~131MB during generation. Pi has 427MB total. TaleVision + Flask use ~170MB. Together that's ~300MB — tight but should work if nothing else is running.
- **Swap thrashing**: model partially loads into swap (126MB swap used during test). This slows generation but works.
- **Timeout**: 180s default timeout may be too short. First generation includes model load time. Consider 300s.
- **Output parsing**: SmolLM-135M is small — it may not always produce clean 3-line haiku + pen name. The parser in `_parse_output()` handles common variations but may need tuning.
- **Concurrent access**: if TaleVision tries to generate while a previous generation is still running, subprocess.run blocks. The 600s refresh interval (10 min) should prevent this since generation takes ~2min.

## CRITICAL SESSION LESSON FOR NEXT CLAUDE

**DO NOT poll SSH commands in a loop or with blocking waits from the Mac.**

The Pi Zero W is extremely slow. SSH commands to it that involve heavy computation (compilation, LLM inference) can take minutes. If you:
1. Launch a long-running SSH command
2. Block waiting for its output with TaskOutput
3. The command takes >5 minutes

...you will get stuck in a loop of timeouts, losing ability to respond to the user.

**Instead:**
- Launch long SSH commands with `nohup ... > /tmp/output.log 2>&1 &` and check the file later
- Or use `run_in_background: true` but DON'T block on TaskOutput — just check periodically when the user asks
- Or better yet, do the testing ON the Pi directly (tell the user to SSH in and run the command themselves)
- For build monitoring: a single `ssh ... "tail -5 logfile"` call is fine. But don't loop or block.

## Files Modified This Session

| File | Status |
|------|--------|
| `talevision/modes/koan.py` | Updated — LLM generation as primary, archive as fallback only |
| `talevision/modes/koan_generator.py` | NEW — subprocess LLM caller + parser + prompt pool |
| `talevision/modes/museo_providers/__init__.py` | Updated — static PROVIDERS = [Met, Cleveland, V&A] |
| `talevision/modes/museo_providers/vanda.py` | NEW — V&A provider |
| `talevision/modes/museo_providers/harvard.py` | DELETED |
| `talevision/modes/museo_providers/smithsonian.py` | Should be deleted (may still exist) |
| `talevision/config/schema.py` | Updated — removed harvard_api_key, smithsonian_api_key |
| `knowledge/PROJECT_KNOWLEDGE.md` | Updated — Koan LLM docs, Museo provider docs |
| `knowledge/DECISIONS.md` | Updated — embedded LLM decision, V&A decision |
| `assets/fonts/CrimsonText-*.ttf` | NEW — haiku font |
| `assets/img/haiku-bg-min.png` | NEW — bamboo ink wash background |
