"""Electric Sheep — AI-generated surreal imagery via Pollinations.ai."""
import io
import json
import logging
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

_POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# ── Surreal prompt pool ──────────────────────────────────────────────────────
# Each entry: (theme, style)
_DREAMS: list[tuple[str, str]] = [
    ("a goldfish piloting a submarine made of cheese", "oil painting"),
    ("an octopus playing chess against a cactus in a barbershop", "vintage illustration"),
    ("a grand piano growing out of a storm cloud above a desert highway", "watercolor"),
    ("a lighthouse made of stacked books on a sea of ink", "woodcut print"),
    ("a bear in a business suit queuing at a cloud ATM", "risograph print"),
    ("a teapot orbiting a tiny planet made of moss", "vintage scientific illustration"),
    ("a bicycle riding itself through a library on fire", "halftone newspaper illustration"),
    ("a cat made entirely of mirrors sitting in a barber's chair", "oil painting"),
    ("a clock melting over the edge of a giant sandwich", "surrealist painting"),
    ("an astronaut tending a garden of neon mushrooms on the moon", "digital illustration"),
    ("a whale swimming through a field of sunflowers at sunset", "watercolor"),
    ("a toaster on trial in a courtroom full of bread loaves", "vintage editorial cartoon"),
    ("two umbrellas arguing under a rainbow", "children's book illustration"),
    ("a snail racing a glacier, crowd cheering wildly", "vintage poster illustration"),
    ("a flock of rubber ducks migrating over the Alps", "oil painting"),
    ("a dentist's waiting room inside a volcano", "comic book panel"),
    ("a grandfather clock full of bees running for office", "retro propaganda poster"),
    ("a librarian made of fog cataloguing clouds", "art nouveau illustration"),
    ("a dog in a lab coat presenting its findings on sticks", "vintage scientific illustration"),
    ("a traffic jam of shopping trolleys on the highway to the sun", "pop art"),
    ("the last vending machine on a deserted island at twilight", "oil painting"),
    ("a chorus of office chairs singing opera in an empty stadium", "watercolor"),
    ("a hot air balloon made of lost mittens floating over a city", "vintage poster"),
    ("a mathematician calculating the weight of fog", "halftone newspaper illustration"),
    ("a mailbox in the middle of the ocean receiving letters from fish", "oil painting"),
    ("a sleeping giant whose beard has become a river delta", "fantasy illustration"),
    ("a convenience store on the back of a slow-moving tortoise", "risograph print"),
    ("three philosophers arguing about the last slice of cake", "Renaissance oil painting"),
    ("a map of a city drawn entirely in pasta", "vintage cartographic illustration"),
    ("a ski slope made of whipped cream with ants for skiers", "children's book illustration"),
    ("a cloud shaped exactly like bureaucracy", "editorial cartoon"),
    ("a retired volcano growing a vineyard in its caldera", "watercolor"),
    ("a parking lot for horses in downtown Tokyo", "street photography style illustration"),
    ("a sommelier tasting a glass of liquid time", "oil painting"),
    ("a supermarket selling only emotions on special offer", "vintage commercial illustration"),
    ("a bird building a nest out of lost Wi-Fi signals", "natural history illustration"),
    ("a wedding between a satellite dish and a weather vane", "folk art"),
    ("a tax inspector auditing a rainbow", "editorial cartoon"),
    ("a committee of clouds voting on the next type of rain", "vintage illustration"),
    ("a mole drilling a metro tunnel through a soufflé", "comic strip"),
    ("a jazz band made of broken appliances playing to an empty fridge", "oil painting"),
    ("a dictionary dreaming of becoming a novel", "surrealist painting"),
    ("a migratory flock of alarm clocks heading south", "vintage natural history illustration"),
    ("the moon working a night shift at a lighthouse", "oil painting"),
    ("a submarine full of accountants exploring a sea of receipts", "vintage editorial cartoon"),
    ("a goat becoming prime minister after a clerical error", "retro political illustration"),
    ("a parking ticket issued to a parked cloud", "editorial cartoon"),
    ("a glacier moving apartments, bubble-wrapped belongings in tow", "oil painting"),
    ("a coral reef made entirely of forgotten passwords", "digital surrealism"),
    ("an elevator that only goes sideways", "architectural illustration"),
    ("a cartographer mapping the inside of a sleeping dog's dream", "fantasy map illustration"),
    ("a bakery run by insomniacs producing only bread that wakes you up", "vintage commercial art"),
    ("a meeting of all the world's left socks", "children's book illustration"),
    ("a bureaucrat filling out a form to request more sunlight", "editorial cartoon"),
    ("a fire station where all the firefighters are candles", "surrealist painting"),
    ("an expedition to the far corner of a very large duvet", "vintage explorer illustration"),
    ("a jury of twelve identical spoons deliberating over a fork", "courtroom illustration"),
    ("a retired compass trying to find meaning in a straight road", "oil painting"),
    ("a river that flows uphill on Tuesdays", "fantasy landscape watercolor"),
    ("a dentist drilling a cavity in a crescent moon", "vintage scientific illustration"),
    ("an annual conference of all things that have been misplaced", "editorial illustration"),
    ("a ghost trying to rent an apartment and failing the background check", "comic illustration"),
    ("a traffic light on a country road with no cars, deeply fulfilled", "oil painting"),
    ("a mirror that shows you what you looked like yesterday", "surrealist painting"),
    ("a library of unwritten books, all checked out", "fantasy illustration"),
    ("a cloud that produces only very small, very local weather events", "watercolor"),
    ("a geologist dating rocks who are clearly out of his league", "vintage editorial cartoon"),
    ("a kettle that whistles in a foreign language", "retro kitchen advertisement illustration"),
    ("a retired thunderstorm teaching lightning to children", "folk art"),
    ("a typewriter running out of letters mid-confession", "noir illustration"),
    ("a solar system where all planets orbit a single lost earring", "vintage scientific illustration"),
    ("a cartographer who only maps places that don't exist yet", "fantasy map"),
    ("a train station for thoughts that never departed", "oil painting"),
    ("a snorkeler in a sea of scattered puzzle pieces", "watercolor"),
    ("an archaeologist excavating yesterday's argument", "vintage illustration"),
    ("a pigeon delivering certified philosophical mail", "editorial cartoon"),
    ("a botanist cataloguing a species of invisible flower", "natural history illustration"),
    ("a demolition crew knocking down a fog bank", "construction worker illustration"),
    ("a deep-sea diver discovering a sunken to-do list", "vintage exploration illustration"),
    ("a fire escape that leads to a better neighbourhood", "oil painting"),
    ("a beekeeper tending hives full of tiny abstract concepts", "vintage natural history illustration"),
    ("an origami swan slowly unfolding its life choices", "surrealist illustration"),
    ("a notary certifying the existence of shadows", "editorial cartoon"),
    ("a sleeping whale dreaming in architecture", "watercolor"),
    ("a balloon animal lawyer making closing arguments", "comic illustration"),
    ("a ship in a bottle inside a larger bottle inside a sea", "oil painting"),
    ("a very patient ant moving the Great Wall stone by stone", "vintage illustration"),
    ("a black hole with a polite sign saying please queue here", "editorial cartoon"),
    ("an orchestra tuning instruments to the sound of distant traffic", "oil painting"),
    ("a dog teaching a seminar on the philosophy of walks", "vintage editorial cartoon"),
    ("a moth holding a farewell party for a light bulb", "folk art"),
    ("a polar bear opening a radiator repair shop", "retro commercial illustration"),
    ("a botanist discovering a flower that blooms only during arguments", "natural history illustration"),
    ("a postman delivering letters to clouds", "whimsical illustration"),
    ("a tired metaphor waiting for a bus that never comes", "surrealist painting"),
    ("a retired comet selling asteroid insurance door to door", "vintage space illustration"),
    ("a fog machine at a philosophy conference that got out of hand", "editorial cartoon"),
    ("a sandwich making a sandwich with smaller sandwiches inside", "pop art"),
    ("a staircase leading to the sound of rain", "oil painting"),
    ("a bird teaching a stone to fly via correspondence course", "vintage illustration"),
    ("a swimming pool filled with unread emails on a summer afternoon", "watercolor"),
]


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default(size=size)


def _truncate(text: str, draw: ImageDraw.ImageDraw, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


class ElectricSheepMode(DisplayMode):
    """Generates and displays surreal AI images via Pollinations.ai.

    Background thread generates one new dream per generation_interval seconds
    and saves it to the archive. render() picks a random dream from the archive
    instantly — no API wait during display.
    """

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.electricsheep
        self._w = config.display.width
        self._h = config.display.height

        fonts_dir = base_dir / "assets" / "fonts"
        self._font_theme = _load_font(fonts_dir / "Signika-Bold.ttf", 22)
        self._font_style  = _load_font(fonts_dir / "Taviraj-Italic.ttf", 17)
        self._font_mono   = _load_font(fonts_dir / "InconsolataNerdFontMono-Regular.ttf", 16)
        self._font_dream  = _load_font(fonts_dir / "Lobster-Regular.ttf", 52)
        self._font_err    = _load_font(fonts_dir / "Signika-Bold.ttf", 26)

        self._archive_dir = base_dir / "cache" / "electricsheep_archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)

        self._stop_event = threading.Event()
        self._gen_thread: Optional[threading.Thread] = None

        self._current_dream: Optional[dict] = None
        self._last_error: str = ""

    # ── DisplayMode interface ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "electricsheep"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        self._stop_event.clear()
        self._gen_thread = threading.Thread(
            target=self._generator_loop,
            daemon=True,
            name="sheep-gen",
        )
        self._gen_thread.start()
        log.info("Electric Sheep: generator thread started")

    def on_deactivate(self) -> None:
        self._stop_event.set()
        if self._gen_thread and self._gen_thread.is_alive():
            self._gen_thread.join(timeout=5)
        log.info("Electric Sheep: generator thread stopped")

    def render(self) -> Image.Image:
        dream = self._pick_dream()
        if dream is None:
            return self._dreaming_screen()
        img_path = self._archive_dir / dream["image_file"]
        if not img_path.exists():
            return self._dreaming_screen()
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as exc:
            log.warning("Electric Sheep: failed to open %s: %s", img_path, exc)
            return self._dreaming_screen()
        img = ImageOps.fit(img, (self._w, self._h), Image.LANCZOS)
        img = self._enhance(img)
        return self._draw_overlay(img, dream)

    def get_state(self) -> ModeState:
        count = len(self._list_archive_files())
        dream = self._current_dream or {}
        return ModeState(
            extra={
                "dream_id": dream.get("id"),
                "theme": dream.get("theme", ""),
                "style": dream.get("style", ""),
                "archive_count": count,
                "last_error": self._last_error,
            }
        )

    # ── Archive helpers ──────────────────────────────────────────────────────

    def _list_archive_files(self) -> list[Path]:
        return sorted(self._archive_dir.glob("*.json"))

    def _pick_dream(self) -> Optional[dict]:
        files = self._list_archive_files()
        if not files:
            return None
        chosen = random.choice(files)
        try:
            entry = json.loads(chosen.read_text(encoding="utf-8"))
            self._current_dream = entry
            return entry
        except Exception:
            return None

    # ── Background generator ─────────────────────────────────────────────────

    def _generator_loop(self) -> None:
        # Generate immediately if archive has < 3 dreams (bootstrap)
        if len(self._list_archive_files()) < 3:
            self._generate_dream()

        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._cfg.generation_interval)
            if self._stop_event.is_set():
                break
            self._generate_dream()
            self._prune_archive()

    def _generate_dream(self) -> None:
        theme, style = random.choice(_DREAMS)
        prompt = f"{theme}, {style}, no text, no words, highly detailed"
        seed = random.randint(1, 999999)
        log.info("Electric Sheep: generating '%s'…", theme[:60])
        t0 = time.time()
        try:
            data = self._fetch_image(prompt, seed)
        except Exception as exc:
            self._last_error = str(exc)
            log.warning("Electric Sheep: generation failed: %s", exc)
            return
        elapsed_ms = int((time.time() - t0) * 1000)
        self._last_error = ""
        self._save_to_archive(theme, style, prompt, seed, data, elapsed_ms)

    def _fetch_image(self, prompt: str, seed: int) -> bytes:
        encoded = urllib.parse.quote(prompt, safe="")
        params = urllib.parse.urlencode({
            "width": self._w,
            "height": self._h,
            "seed": seed,
            "model": "flux",
            "nologo": "true",
            "nofeed": "true",
        })
        url = f"{_POLLINATIONS_URL.format(prompt=encoded)}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": _UA})

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=self._cfg.timeout) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt == 0:
                    log.info("Electric Sheep: 429, waiting 90s before retry")
                    self._stop_event.wait(timeout=90)
                    continue
                raise RuntimeError(f"HTTP {exc.code}") from exc
            except Exception as exc:
                raise RuntimeError(str(exc)) from exc
        raise RuntimeError("Failed after retry")

    def _save_to_archive(
        self,
        theme: str,
        style: str,
        prompt: str,
        seed: int,
        data: bytes,
        elapsed_ms: int,
    ) -> None:
        files = self._list_archive_files()
        new_id = len(files) + 1
        ts = datetime.now(timezone.utc)
        ts_str = ts.strftime("%Y%m%d-%H%M%S")
        slug = theme.replace(" ", "-")[:40]
        base_name = f"{ts_str}_{slug}"

        img_name = f"{base_name}.jpg"
        img_path = self._archive_dir / img_name
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img.save(str(img_path), format="JPEG", quality=92)
        except Exception as exc:
            log.warning("Electric Sheep: failed to save image: %s", exc)
            return

        meta = {
            "id": new_id,
            "timestamp": ts.isoformat(),
            "theme": theme,
            "style": style,
            "prompt": prompt,
            "seed": seed,
            "width": self._w,
            "height": self._h,
            "model": "flux",
            "generation_time_ms": elapsed_ms,
            "image_file": img_name,
        }
        json_path = self._archive_dir / f"{base_name}.json"
        json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Electric Sheep: saved dream #%d — %s", new_id, theme[:60])

    def _prune_archive(self) -> None:
        max_a = self._cfg.max_archive
        files = self._list_archive_files()
        if len(files) <= max_a:
            return
        to_remove = files[:len(files) - max_a]
        for jf in to_remove:
            img = jf.with_suffix(".jpg")
            jf.unlink(missing_ok=True)
            img.unlink(missing_ok=True)

    # ── Rendering ────────────────────────────────────────────────────────────

    def _enhance(self, img: Image.Image) -> Image.Image:
        img = ImageEnhance.Brightness(img).enhance(self._cfg.brightness)
        img = ImageEnhance.Contrast(img).enhance(self._cfg.contrast)
        img = ImageEnhance.Color(img).enhance(self._cfg.color)
        return img

    def _draw_overlay(self, img: Image.Image, dream: dict) -> Image.Image:
        w, h = img.size
        band_h = 95

        overlay = Image.new("RGBA", (w, band_h), (0, 0, 0, 245))
        draw = ImageDraw.Draw(overlay)

        theme = dream.get("theme", "")
        style = dream.get("style", "")
        dream_id = dream.get("id", "?")
        ts_str = ""
        try:
            ts_str = datetime.fromisoformat(dream["timestamp"]).strftime("%-d %B %Y")
        except Exception:
            pass

        max_w = w - 32
        theme_text = _truncate(theme.capitalize(), draw, self._font_theme, max_w)
        draw.text((16, 8), theme_text, font=self._font_theme, fill=(255, 255, 255))
        draw.text((16, 38), style, font=self._font_style, fill=(180, 180, 180))

        clock_str = datetime.now().strftime("%H:%M")
        right_text = f"#{dream_id} · {ts_str}"
        draw.text((16, 65), right_text, font=self._font_mono, fill=(130, 130, 130))
        clock_w = int(draw.textlength(clock_str, font=self._font_mono))
        draw.text((w - clock_w - 16, 65), clock_str, font=self._font_mono, fill=(130, 130, 130))

        img_rgba = img.convert("RGBA")
        img_rgba.paste(overlay, (0, h - band_h), overlay)
        return img_rgba.convert("RGB")

    def _dreaming_screen(self) -> Image.Image:
        img = Image.new("RGB", (self._w, self._h), (8, 8, 20))
        draw = ImageDraw.Draw(img)
        cx = self._w // 2

        draw.text((cx, 180), "electric sheep", font=self._font_dream,
                  fill=(120, 60, 200), anchor="mm")
        draw.text((cx, 250), "do e-ink displays dream of electric sheep?",
                  font=self._font_style, fill=(70, 70, 100), anchor="mm")

        if self._last_error:
            draw.text((cx, 320), f"last error: {self._last_error[:80]}",
                      font=self._font_mono, fill=(80, 40, 40), anchor="mm")
        else:
            draw.text((cx, 320), "generating first dream…",
                      font=self._font_mono, fill=(60, 60, 80), anchor="mm")

        clock_str = datetime.now().strftime("%H:%M")
        draw.text((self._w - 20, self._h - 24), clock_str,
                  font=self._font_mono, fill=(60, 60, 80), anchor="rm")
        return img
