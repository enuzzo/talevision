"""Local LLM haiku generator for Koan mode via llama.zero / llama.cpp."""
import logging
import re
import subprocess
import time
from pathlib import Path
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
    "Write a haiku (3 lines, 5-7-5 syllables). "
    "Sign with a pen name.\n"
    "Format:\nfirst line\nsecond line\nthird line\n— Name"
)


def generate_haiku(
    llm_binary: str,
    llm_model: str,
    seed_word: str,
    timeout: int = 900,
) -> Optional[dict]:
    """Run local LLM and parse haiku output.

    Returns dict with keys: lines, author_name, generation_time_ms
    or None on failure.
    """
    prompt = (
        f"<|im_start|>system\n{_SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\nTheme: {seed_word}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    cmd = [
        llm_binary,
        "-m", llm_model,
        "-p", prompt,
        "-n", "60",
        "--temp", "0.9",
        "--top-p", "0.95",
        "--repeat-penalty", "1.1",
        "--log-disable",
        "--no-display-prompt",
        "-e",
    ]

    log.info("Koan LLM: generating (seed=%s, timeout=%ds)", seed_word, timeout)
    t0 = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if result.returncode != 0:
            log.warning("Koan LLM exited with code %d: %s",
                        result.returncode, result.stderr[:200])
            return None

        raw = result.stdout.strip()
        log.debug("Koan LLM raw output:\n%s", raw)
        return _parse_output(raw, elapsed_ms)

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.warning("Koan LLM timed out after %dms", elapsed_ms)
        return None
    except FileNotFoundError:
        log.error("Koan LLM binary not found: %s", llm_binary)
        return None
    except Exception as exc:
        log.error("Koan LLM unexpected error: %s", exc)
        return None


def _parse_output(raw: str, elapsed_ms: int) -> Optional[dict]:
    """Parse LLM output into haiku lines + pen name."""
    # Remove the prompt echo if present
    if "<|im_start|>" in raw:
        parts = raw.split("<|im_start|>assistant")
        raw = parts[-1] if len(parts) > 1 else raw

    # Clean up
    raw = raw.replace("<|im_end|>", "").strip()

    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    # Look for pen name (line starting with em dash or hyphen)
    pen_name = ""
    haiku_lines = []
    for line in lines:
        if line.startswith(("\u2014", "—", "- ", "– ")):
            pen_name = re.sub(r'^[\u2014\-–]\s*', '', line).strip()
        elif len(haiku_lines) < 3:
            haiku_lines.append(line)

    if len(haiku_lines) < 3:
        log.warning("Koan LLM: could not parse 3 haiku lines from: %s", raw[:200])
        return None

    if not pen_name:
        pen_name = "Unnamed"

    return {
        "lines": haiku_lines[:3],
        "author_name": pen_name,
        "generation_time_ms": elapsed_ms,
    }


def get_random_prompt() -> str:
    """Return a random introspective prompt question."""
    import random
    return random.choice(_PROMPTS)
