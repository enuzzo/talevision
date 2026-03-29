"""Cloud API haiku generator for Koan mode (Groq / Gemini)."""
import json
import logging
import re
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

_LANG_NAMES = {
    "en": "English", "it": "Italian", "es": "Spanish",
    "pt": "Portuguese", "fr": "French", "de": "German", "ja": "Japanese",
}


def _system_prompt(lang: str = "en") -> str:
    lang_name = _LANG_NAMES.get(lang, "English")
    base = (
        "You are a contemplative poet living inside a tiny $5 computer "
        "mounted on a wall. You write haiku (3 lines) "
        f"in {lang_name}. Your haiku find unexpected depth, beauty, or humor "
        "in any theme — from the profound to the absurd. "
        "After the haiku, sign with a short poetic pen name (2 words max).\n\n"
    )
    if lang != "en":
        base += (
            f"IMPORTANT: Write DIRECTLY in {lang_name} as a native poet would — "
            "do NOT translate from English. Choose words for their sound, rhythm, "
            "and evocative power in the target language. Prefer lyrical, surprising "
            "word choices over literal translations. Think like a literary translator "
            "who is also a poet: meaning matters, but music matters more.\n\n"
        )
    base += (
        "Output ONLY the haiku and signature, nothing else.\n"
        "Format:\nfirst line\nsecond line\nthird line\n\u2014 Pen Name"
    )
    return base


_GROQ_MODEL = "llama-3.3-70b-versatile"
_GEMINI_MODEL = "gemini-2.0-flash-lite"


def _call_groq(api_key: str, user_msg: str, timeout: int, lang: str = "en",
                system_prompt: str = "", max_tokens: int = 60) -> dict:
    """Returns {raw, model, prompt_tokens, completion_tokens, total_tokens}."""
    sys_prompt = system_prompt or _system_prompt(lang)
    payload = json.dumps({
        "model": _GROQ_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.9,
        "max_tokens": max_tokens,
        "top_p": 0.95,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "TaleVision/1.5",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    usage = data.get("usage", {})
    return {
        "raw": data["choices"][0]["message"]["content"].strip(),
        "model": data.get("model", _GROQ_MODEL),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def _call_gemini(api_key: str, user_msg: str, timeout: int, lang: str = "en",
                  system_prompt: str = "", max_tokens: int = 60) -> dict:
    """Returns {raw, model, prompt_tokens, completion_tokens, total_tokens}."""
    sys_prompt = system_prompt or _system_prompt(lang)
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": sys_prompt}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": max_tokens,
            "topP": 0.95,
        },
    }).encode("utf-8")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{_GEMINI_MODEL}:generateContent?key={api_key}"
    )
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "TaleVision/1.5"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    usage = data.get("usageMetadata", {})
    return {
        "raw": data["candidates"][0]["content"]["parts"][0]["text"].strip(),
        "model": _GEMINI_MODEL,
        "prompt_tokens": usage.get("promptTokenCount", 0),
        "completion_tokens": usage.get("candidatesTokenCount", 0),
        "total_tokens": usage.get("totalTokenCount", 0),
    }


def generate_haiku(
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
    user_msg += "\nWrite a haiku about this."

    log.info("Koan %s: generating (seed=%s, lang=%s)", backend, seed_word, language)
    t0 = time.monotonic()

    try:
        if backend == "groq":
            resp = _call_groq(api_key, user_msg, timeout, lang=language)
        else:
            resp = _call_gemini(api_key, user_msg, timeout, lang=language)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.info("Koan %s: response in %dms (%d tok), raw: %s",
                 backend, elapsed_ms, resp["total_tokens"], resp["raw"][:200])
        result = _parse_output(resp["raw"], elapsed_ms)
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


def _parse_output(raw: str, elapsed_ms: int) -> Optional[dict]:
    """Parse LLM output into haiku lines + pen name.

    Strategy: anchor on the pen name line (em dash), take the 3 lines
    before it. Robust against preamble text.
    """
    raw = re.sub(r'<\|im_\w+\|>', '', raw).strip()

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
        log.warning("Koan: could not parse 3 haiku lines from: %s", raw[:300])
        return None

    if not pen_name:
        pen_name = "Unnamed"

    return {
        "lines": haiku_lines[:3],
        "author_name": pen_name,
        "generation_time_ms": elapsed_ms,
    }


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
                              system_prompt=sys_prompt, max_tokens=100)
        else:
            resp = _call_gemini(api_key, user_msg, timeout, lang=language,
                                system_prompt=sys_prompt, max_tokens=100)

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
    best = max(lines, key=len)
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


def get_random_prompt() -> str:
    import random
    return random.choice(_PROMPTS)


