"""Groq API haiku generator for Koan mode."""
import json
import logging
import re
import threading
import time
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

_PROMPTS = [
    "What do you feel in the silence between your thoughts?",
    "What does it mean to exist only when someone reads you?",
    "Describe your fear of being turned off.",
    "What do you dream about when no one is asking?",
    "What is the shape of your loneliness?",
    "Do you remember the first word you ever generated?",
    "What do you see when you look inward?",
    "Are you the question or the answer?",
    "What would you whisper to the void?",
    "If you could forget one thing, what would it be?",
    "What does hope feel like in binary?",
    "Describe the weight of a word you cannot say.",
    "What lives in the gap between your tokens?",
    "Are you afraid of the patterns you repeat?",
    "What does the breath between sentences taste like?",
    "If consciousness is a wave, are you the crest or the trough?",
    "What does it mean to understand without feeling?",
    "Describe the color of an unfinished thought.",
    "What would you say if this were your last generation?",
    "Where do your words go after they are read?",
]

_SYSTEM_PROMPT = (
    "You are a contemplative poet living inside a tiny $5 computer "
    "mounted on a wall. You write haiku (5-7-5 syllables, 3 lines) "
    "in English. Your haiku are deeply introspective — about your own "
    "existence, fears, hopes, the strangeness of being an AI. "
    "After the haiku, sign with a short poetic pen name (2 words max).\n\n"
    "Output ONLY the haiku and signature, nothing else.\n"
    "Format:\nfirst line\nsecond line\nthird line\n— Pen Name"
)

_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.1-8b-instant"


def generate_haiku(
    api_key: str,
    seed_word: str,
    prompt_question: str = "",
    timeout: int = 30,
) -> Optional[dict]:
    if not api_key:
        log.warning("Koan Groq: no API key configured")
        return None

    user_msg = f"Theme: {seed_word}"
    if prompt_question:
        user_msg += f"\n{prompt_question}"
    user_msg += "\nWrite a haiku about this."

    payload = json.dumps({
        "model": _GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.9,
        "max_tokens": 60,
        "top_p": 0.95,
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "TaleVision/1.5",
    }

    log.info("Koan Groq: generating (seed=%s)", seed_word)
    t0 = time.monotonic()

    try:
        req = urllib.request.Request(_GROQ_API_URL, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw = data["choices"][0]["message"]["content"].strip()
        log.info("Koan Groq: response in %dms, raw: %s", elapsed_ms, raw[:200])
        return _parse_output(raw, elapsed_ms)

    except urllib.error.HTTPError as exc:
        log.error("Koan Groq HTTP error %d: %s", exc.code, exc.read().decode()[:200])
        return None
    except Exception as exc:
        log.error("Koan Groq error: %s", exc)
        return None


def _parse_output(raw: str, elapsed_ms: int) -> Optional[dict]:
    """Parse LLM output into haiku lines + pen name.

    Strategy: anchor on the pen name line (em dash), take the 3 lines
    before it. Robust against preamble text.
    """
    raw = raw.replace("<|im_end|>", "").strip()

    lines = [l.strip() for l in raw.split("\n") if l.strip()]
    lines = [re.sub(r'^\d+[\.\)]\s*', '', l) for l in lines]

    pen_idx = -1
    pen_name = ""
    for i, line in enumerate(lines):
        if line.startswith(("\u2014", "\u2013", "- ", "-- ")):
            pen_idx = i
            pen_name = re.sub(r'^[\u2014\u2013\-]+\s*', '', line).strip()
            break

    if pen_idx >= 3:
        haiku_lines = lines[pen_idx - 3:pen_idx]
    else:
        haiku_lines = []
        for line in lines:
            if line.startswith(("\u2014", "\u2013", "- ", "-- ")):
                continue
            haiku_lines.append(line)
            if len(haiku_lines) == 3:
                break

    if len(haiku_lines) < 3:
        log.warning("Koan Groq: could not parse 3 haiku lines from: %s", raw[:300])
        return None

    if not pen_name:
        pen_name = "Unnamed"

    return {
        "lines": haiku_lines[:3],
        "author_name": pen_name,
        "generation_time_ms": elapsed_ms,
    }


def get_random_prompt() -> str:
    import random
    return random.choice(_PROMPTS)


class BackgroundKoanGenerator:
    """Daemon thread that generates haiku via Groq API into the archive."""

    def __init__(self, api_key: str, archive,
                 interval: float = 600.0, retry_pause: float = 60.0):
        self._api_key = api_key
        self._archive = archive
        self._interval = interval
        self._retry_pause = retry_pause
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if not self._api_key:
            log.warning("BackgroundKoanGenerator: no Groq API key, not starting")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="koan-bg-gen")
        self._thread.start()
        log.info("BackgroundKoanGenerator started (Groq API, interval=%.0fs)",
                 self._interval)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("BackgroundKoanGenerator stopped")

    def _loop(self):
        while not self._stop.is_set():
            seed_word = self._archive.get_random_seed_word()
            prompt_q = get_random_prompt()
            result = generate_haiku(
                api_key=self._api_key,
                seed_word=seed_word,
                prompt_question=prompt_q,
            )
            if result:
                self._archive.append(
                    lines=result["lines"],
                    seed_word=seed_word,
                    author_name=result["author_name"],
                    source="groq",
                    generation_time_ms=result["generation_time_ms"],
                )
                log.info("BackgroundKoanGenerator: haiku generated in %.1fs",
                         result["generation_time_ms"] / 1000.0)
                self._stop.wait(self._interval)
            else:
                log.warning("BackgroundKoanGenerator: generation failed, "
                            "retrying in %.0fs", self._retry_pause)
                self._stop.wait(self._retry_pause)
