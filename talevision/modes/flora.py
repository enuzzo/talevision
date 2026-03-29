"""Flora mode — generative botanical art via L-system grammars."""
import json
import math
import random
import logging
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from talevision.config.schema import AppConfig
from talevision.modes.base import DisplayMode, ModeState

log = logging.getLogger(__name__)

# ── Palette ──────────────────────────────────────────────────────────────────
_BG_WHITE    = (255, 255, 255)
_BG_CREAM    = (255, 250, 240)
_DARK_NAVY   = (26, 26, 46)
_TEXT_NAVY   = (26, 26, 60)
_TEXT_GRAY   = (120, 115, 108)
_TEXT_LIGHT  = (180, 174, 166)
_SEP_LINE    = (218, 212, 204)

_TRUNK_DARK  = (72, 42, 18)
_TRUNK_MID   = (98, 62, 28)
_STEM_DARK   = (34, 90, 22)
_STEM_MID    = (52, 128, 38)
_STEM_LIGHT  = (72, 158, 56)
_LEAF_GREEN  = (90, 172, 64)
_LEAF_PALE   = (120, 190, 80)

_FLWR_RED    = (200, 40, 40)
_FLWR_ORANGE = (218, 112, 22)
_FLWR_YELLOW = (208, 178, 18)
_FLWR_PINK   = (210, 82, 128)
_FLWR_BLUE   = (48, 108, 200)
_FLWR_CENTRE = (240, 210, 60)

# ── Species database ──────────────────────────────────────────────────────────
_SPECIES = [
    {
        "id": "fern",
        "genera":   ["Pteridium", "Dryopteris", "Adiantum", "Polypodium"],
        "epithets": ["aquilinum", "filix-mas", "capillus-veneris", "vulgare"],
        "family": "Polypodiaceae", "order": "Polypodiales",
        "axiom": "X",
        "rules": {"X": "F+[[X]-X]-F[-FX]+X", "F": "FF"},
        "angle": 25.0, "iterations": 5,
        "flower_color": None, "flower_prob": 0.0,
    },
    {
        "id": "tree",
        "genera":   ["Quercus", "Betula", "Fraxinus", "Acer"],
        "epithets": ["robur", "pendula", "excelsior", "campestre"],
        "family": "Fagaceae", "order": "Fagales",
        "axiom": "F",
        "rules": {"F": "F[+F][-F]F"},
        "angle": 25.0, "iterations": 4,
        "flower_color": None, "flower_prob": 0.0,
    },
    {
        "id": "bush",
        "genera":   ["Myrtus", "Viburnum", "Ligustrum", "Buxus"],
        "epithets": ["communis", "opulus", "ovalifolium", "sempervirens"],
        "family": "Myrtaceae", "order": "Myrtales",
        "axiom": "F",
        "rules": {"F": "FF+[+F-F-F]-[-F+F+F]"},
        "angle": 22.0, "iterations": 4,
        "flower_color": _FLWR_PINK, "flower_prob": 0.45,
    },
    {
        "id": "vine",
        "genera":   ["Hedera", "Parthenocissus", "Vitis", "Wisteria"],
        "epithets": ["helix", "quinquefolia", "vinifera", "sinensis"],
        "family": "Araliaceae", "order": "Apiales",
        "axiom": "X",
        "rules": {"X": "F-[[X]+X]+F[+FX]-X", "F": "FF"},
        "angle": 22.0, "iterations": 5,
        "flower_color": _FLWR_BLUE, "flower_prob": 0.30,
    },
    {
        "id": "flower",
        "genera":   ["Rosa", "Hibiscus", "Papaver", "Magnolia"],
        "epithets": ["canina", "sabdariffa", "rhoeas", "grandiflora"],
        "family": "Rosaceae", "order": "Rosales",
        "axiom": "F",
        "rules": {"F": "F[+F][-F][++F][--F]F"},
        "angle": 36.0, "iterations": 3,
        "flower_color": _FLWR_RED, "flower_prob": 0.60,
    },
    {
        "id": "bamboo",
        "genera":   ["Phyllostachys", "Bambusa", "Fargesia", "Dendrocalamus"],
        "epithets": ["aurea", "vulgaris", "murielae", "giganteus"],
        "family": "Poaceae", "order": "Poales",
        "axiom": "A",
        "rules": {"A": "FFF[++FF][--FF]A"},
        "angle": 30.0, "iterations": 5,
        "flower_color": _FLWR_YELLOW, "flower_prob": 0.18,
    },
    {
        "id": "reed",
        "genera":   ["Phragmites", "Arundo", "Typha", "Calamagrostis"],
        "epithets": ["australis", "donax", "latifolia", "epigejos"],
        "family": "Poaceae", "order": "Poales",
        "axiom": "F",
        "rules": {"F": "FF[+F][-F]"},
        "angle": 18.0, "iterations": 5,
        "flower_color": _FLWR_ORANGE, "flower_prob": 0.30,
    },
    {
        "id": "spring",
        "genera":   ["Narcissus", "Galanthus", "Hyacinthus", "Tulipa"],
        "epithets": ["poeticus", "nivalis", "orientalis", "sylvestris"],
        "family": "Amaryllidaceae", "order": "Asparagales",
        "axiom": "X",
        "rules": {"X": "F[+X]F[-X]+X", "F": "FF"},
        "angle": 20.0, "iterations": 5,
        "flower_color": _FLWR_YELLOW, "flower_prob": 0.45,
    },
]

_MAX_STR_LEN = 80_000
_PLANT_PANEL_W = 500
_FOOTER_H = 44
_MARGIN = 18
_LABEL_X = 504
_LABEL_PAD = 20


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default(size=size)


def _lsystem_string(axiom: str, rules: dict, iterations: int) -> str:
    s = axiom
    for _ in range(iterations):
        s = "".join(rules.get(c, c) for c in s)
        if len(s) > _MAX_STR_LEN:
            s = s[:_MAX_STR_LEN]
            break
    return s


def _turtle_bounds(s: str, angle_deg: float) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) with unit step, start at (0,0), direction up."""
    x, y = 0.0, 0.0
    direction = -90.0
    stack: list = []
    min_x = max_x = 0.0
    min_y = max_y = 0.0

    for cmd in s:
        if cmd == "F":
            x += math.cos(math.radians(direction))
            y += math.sin(math.radians(direction))
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
        elif cmd == "+":
            direction -= angle_deg
        elif cmd == "-":
            direction += angle_deg
        elif cmd == "[":
            stack.append((x, y, direction))
        elif cmd == "]" and stack:
            x, y, direction = stack.pop()

    return (min_x, min_y, max_x, max_y)


def _draw_leaf(draw: ImageDraw.ImageDraw, x: float, y: float, direction: float,
               size: int, rng: random.Random) -> None:
    """Draw a small leaf cluster at branch tip."""
    ang = math.radians(direction)
    perp = math.radians(direction + 90)
    spread = size * 0.8
    for dx, dy in [
        (math.cos(ang) * size * 0.5, math.sin(ang) * size * 0.5),
        (math.cos(perp) * spread, math.sin(perp) * spread),
        (-math.cos(perp) * spread, -math.sin(perp) * spread),
    ]:
        lx, ly = x + dx, y + dy
        r = max(1, size - rng.randint(0, 1))
        col = rng.choice([_LEAF_GREEN, _LEAF_PALE, _STEM_MID])
        draw.ellipse([(lx - r, ly - r), (lx + r, ly + r)], fill=col)


def _draw_flower(draw: ImageDraw.ImageDraw, x: float, y: float,
                 color: tuple, depth: int) -> None:
    """Draw a bold flower: petals + yellow centre."""
    r = max(5, 9 - depth)
    # Four petals as offset ellipses
    for ang in (0, 90, 180, 270):
        ox = math.cos(math.radians(ang)) * r * 0.6
        oy = math.sin(math.radians(ang)) * r * 0.6
        pr = max(3, r - 1)
        draw.ellipse([(x + ox - pr, y + oy - pr), (x + ox + pr, y + oy + pr)], fill=color)
    # Centre
    cr = max(2, r // 3)
    draw.ellipse([(x - cr, y - cr), (x + cr, y + cr)], fill=_FLWR_CENTRE)


def _turtle_draw(
    draw: ImageDraw.ImageDraw,
    s: str,
    start_x: float,
    start_y: float,
    step: float,
    angle_deg: float,
    species: dict,
    rng: random.Random,
) -> None:
    x, y = start_x, start_y
    direction = -90.0
    stack: list = []
    depth = 0
    is_tree_like = species["id"] in ("tree", "bush", "vine")

    for cmd in s:
        if cmd == "F":
            jitter = rng.uniform(-2.5, 2.5)
            rad = math.radians(direction + jitter)
            nx = x + step * math.cos(rad)
            ny = y + step * math.sin(rad)
            if is_tree_like:
                if depth == 0:
                    color, width = _TRUNK_DARK, 5
                elif depth == 1:
                    color, width = _TRUNK_MID, 4
                elif depth == 2:
                    color, width = _STEM_DARK, 3
                elif depth == 3:
                    color, width = _STEM_MID, 2
                else:
                    color, width = _STEM_LIGHT, 1
            else:
                if depth == 0:
                    color, width = _STEM_DARK, 3
                elif depth <= 2:
                    color, width = _STEM_MID, 2
                elif depth <= 4:
                    color, width = _STEM_LIGHT, 1
                else:
                    color, width = _LEAF_GREEN, 1
            draw.line([(x, y), (nx, ny)], fill=color, width=width)
            x, y = nx, ny
        elif cmd == "+":
            direction -= angle_deg
        elif cmd == "-":
            direction += angle_deg
        elif cmd == "[":
            stack.append((x, y, direction, depth))
            depth += 1
        elif cmd == "]" and stack:
            tip_x, tip_y = x, y
            tip_dir = direction
            x, y, direction, depth = stack.pop()
            fc = species.get("flower_color")
            fp = species.get("flower_prob", 0.0)
            if fc and rng.random() < fp:
                _draw_flower(draw, tip_x, tip_y, fc, depth)
            else:
                leaf_size = max(2, 5 - min(depth, 4))
                _draw_leaf(draw, tip_x, tip_y, tip_dir, leaf_size, rng)


class FloraMode(DisplayMode):

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.flora
        self._display = config.display
        self._base_dir = base_dir

        fonts = base_dir / "assets" / "fonts"
        self._font_specimen  = _load_font(fonts / "Signika-Bold.ttf", 18)
        self._font_genus     = _load_font(fonts / "Lobster-Regular.ttf", 38)
        self._font_epithet   = _load_font(fonts / "Taviraj-Italic.ttf", 24)
        self._font_detail    = _load_font(fonts / "Taviraj-Regular.ttf", 17)
        self._font_footer    = _load_font(fonts / "Signika-Bold.ttf", 16)
        self._font_footer_sm = _load_font(fonts / "InconsolataNerdFontMono-Bold.ttf", 15)
        self._font_formula   = _load_font(fonts / "InconsolataNerdFontMono-Bold.ttf", 12)

        self._last_species_id = ""
        self._last_genus = ""
        self._last_epithet = ""
        self._cache_path = base_dir / "cache" / "flora_frame.png"
        self._archive_dir = base_dir / "cache" / "flora_archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        self._last_archive_date = ""

    @property
    def name(self) -> str:
        return "flora"

    @property
    def refresh_interval(self) -> int:
        return self._cfg.refresh_interval

    def on_activate(self) -> None:
        log.info("Flora mode activated")

    def render(self) -> Image.Image:
        w, h = self._display.width, self._display.height
        today = date.today()
        now = datetime.now()
        rng = random.Random(now.isoformat())

        species = rng.choice(_SPECIES)
        genus   = rng.choice(species["genera"])
        epithet = rng.choice(species["epithets"])
        specimen_num = today.toordinal() % 9999 + 1

        self._last_species_id = species["id"]
        self._last_genus = genus
        self._last_epithet = epithet

        log.info("Flora: rendering %s %s (specimen #%04d)", genus, epithet, specimen_num)

        img = self._compose(w, h, species, genus, epithet, specimen_num, today, rng)

        try:
            img.save(str(self._cache_path))
        except Exception:
            pass

        self._save_archive(img, species, genus, epithet, specimen_num, today)

        return img

    def get_state(self) -> ModeState:
        return ModeState(mode="flora", extra={
            "species": self._last_species_id,
            "genus": self._last_genus,
            "epithet": self._last_epithet,
            "archive_count": len(list(self._archive_dir.glob("*.json"))),
        })

    def _trim_archive(self) -> None:
        max_a = getattr(self._cfg, "max_archive", 1000)
        json_files = sorted(self._archive_dir.glob("*.json"))
        overflow = len(json_files) - max_a
        if overflow <= 0:
            return
        for old_json in json_files[:overflow]:
            try:
                old_json.unlink()
                old_png = old_json.with_suffix(".png")
                if old_png.exists():
                    old_png.unlink()
                log.info("Flora archive: pruned %s (cap=%d)", old_json.name, max_a)
            except Exception as exc:
                log.warning("Flora archive: prune failed: %s", exc)

    def _save_archive(
        self,
        img: "Image.Image",
        species: dict,
        genus: str,
        epithet: str,
        specimen_num: int,
        today: date,
    ) -> None:
        date_str = today.isoformat()
        if self._last_archive_date == date_str:
            return
        json_path = self._archive_dir / f"{date_str}.json"
        png_path = self._archive_dir / f"{date_str}.png"
        if json_path.exists() and png_path.exists():
            self._last_archive_date = date_str
            return
        entry = {
            "date": date_str,
            "specimen_num": specimen_num,
            "species_id": species["id"],
            "genus": genus,
            "epithet": epithet,
            "family": species["family"],
            "order": species["order"],
            "location": self._cfg.location,
        }
        try:
            json_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
            img.save(str(png_path), format="PNG", optimize=True)
            self._last_archive_date = date_str
            log.info("Flora archive: saved %s (%s %s #%04d)", date_str, genus, epithet, specimen_num)
            self._trim_archive()
        except Exception as exc:
            log.warning("Flora archive: save failed: %s", exc)

    def _compose(
        self,
        w: int,
        h: int,
        species: dict,
        genus: str,
        epithet: str,
        specimen_num: int,
        today: date,
        rng: random.Random,
    ) -> Image.Image:
        canvas = Image.new("RGB", (w, h), _BG_WHITE)
        draw = ImageDraw.Draw(canvas)

        # Cream label panel background
        draw.rectangle([(_LABEL_X, 0), (w, h - _FOOTER_H)], fill=_BG_CREAM)

        # Vertical separator line
        draw.rectangle([(_LABEL_X - 2, 0), (_LABEL_X, h - _FOOTER_H)], fill=_SEP_LINE)

        # ── L-system ────────────────────────────────────────────────────────
        s = _lsystem_string(species["axiom"], species["rules"], species["iterations"])

        plant_panel_h = h - _FOOTER_H - _MARGIN
        usable_w = _PLANT_PANEL_W - 2 * _MARGIN

        min_x, min_y, max_x, max_y = _turtle_bounds(s, species["angle"])
        tree_w = max_x - min_x
        tree_h = max_y - min_y  # in PIL y-down: max_y is root, min_y is top

        if tree_w > 0 and tree_h > 0:
            scale = min(usable_w / tree_w, plant_panel_h / tree_h) * 0.88
        elif tree_h > 0:
            scale = plant_panel_h / tree_h * 0.88
        elif tree_w > 0:
            scale = usable_w / tree_w * 0.88
        else:
            scale = 20.0

        step = max(scale, 1.0)

        # Translate so plant is bottom-centered in the plant panel
        plant_cx = (min_x + max_x) / 2 * step
        plant_bottom = max_y * step
        start_x = (_PLANT_PANEL_W / 2) - plant_cx
        start_y = (h - _FOOTER_H - _MARGIN) - plant_bottom

        _turtle_draw(draw, s, start_x, start_y, step, species["angle"], species, rng)

        # ── Label card ────────────────────────────────────────────────────────
        lx = _LABEL_X + _LABEL_PAD
        label_inner_w = w - lx - _LABEL_PAD
        div_w = min(label_inner_w, 220)

        y = 28

        # "Specimen #XXXX" — bold, mid-dark
        draw.text((lx, y), f"Specimen  #{specimen_num:04d}", font=self._font_specimen, fill=_TEXT_GRAY)
        y += 28

        # Genus name (Lobster, larger)
        genus_text = genus
        bbox = draw.textbbox((0, 0), genus_text, font=self._font_genus)
        if (bbox[2] - bbox[0]) > label_inner_w:
            genus_text = genus_text[:10] + "…"
        draw.text((lx, y), genus_text, font=self._font_genus, fill=_TEXT_NAVY)
        y += (bbox[3] - bbox[1]) + 4

        # Epithet (italic, bigger and darker)
        draw.text((lx, y), epithet, font=self._font_epithet, fill=_TEXT_NAVY)
        y += 34

        # Separator
        draw.line([(lx, y), (lx + div_w, y)], fill=_TEXT_GRAY, width=2)
        y += 14

        # Family / Order — bigger and darker
        draw.text((lx, y), f"Fam.  {species['family']}", font=self._font_detail, fill=_TEXT_NAVY)
        y += 24
        draw.text((lx, y), f"Ord.  {species['order']}", font=self._font_detail, fill=_TEXT_NAVY)
        y += 30

        # Separator
        draw.line([(lx, y), (lx + div_w, y)], fill=_TEXT_GRAY, width=2)
        y += 14

        # Observation date — both label and text darker/bigger
        try:
            from babel.dates import format_date
            date_str = format_date(today, "d MMMM yyyy", locale="en")
        except Exception:
            date_str = today.strftime("%d %B %Y")

        draw.text((lx, y), "Observed", font=self._font_detail, fill=_TEXT_GRAY)
        y += 24
        draw.text((lx, y), date_str, font=self._font_detail, fill=_TEXT_NAVY)
        y += 26

        # Location (optional)
        if self._cfg.location:
            draw.text((lx, y), self._cfg.location, font=self._font_detail, fill=_TEXT_GRAY)
            y += 26

        # Separator
        draw.line([(lx, y), (lx + div_w, y)], fill=_SEP_LINE, width=2)
        y += 12

        # L-system formula — Inconsolata mono, strong visual contrast
        for sym, rule in species["rules"].items():
            line = f"{sym} \u2192 {rule}"
            if len(line) > 26:
                line = line[:24] + "\u2026"
            draw.text((lx, y), line, font=self._font_formula, fill=_TEXT_GRAY)
            y += 17
        draw.text(
            (lx, y),
            f"\u03b1 = {species['angle']:.0f}\u00b0   n = {species['iterations']}",
            font=self._font_formula,
            fill=_TEXT_LIGHT,
        )

        # ── Footer bar ────────────────────────────────────────────────────────
        fy = h - _FOOTER_H
        draw.rectangle([(0, fy), (w, h)], fill=_DARK_NAVY)

        footer_y = fy + (_FOOTER_H - 16) // 2

        # Left: "FLORA"
        draw.text((_MARGIN, footer_y), "FLORA", font=self._font_footer, fill=(255, 255, 255))

        # Right: HH:MM · Weekday DD Mon
        now = datetime.now()
        time_str = f"{now.strftime('%H:%M')}  \u00b7  {now.strftime('%a %d %b').upper()}"
        bbox_t = draw.textbbox((0, 0), time_str, font=self._font_footer_sm)
        draw.text((w - (bbox_t[2] - bbox_t[0]) - _MARGIN, footer_y + 1), time_str,
                  font=self._font_footer_sm, fill=(255, 255, 255))

        # Centre: seed · species · iter
        seed_info = f"seed {today.strftime('%Y%m%d')}  \u00b7  {species['id']}  \u00b7  iter {species['iterations']}"
        bbox_s = draw.textbbox((0, 0), seed_info, font=self._font_footer_sm)
        cx = w // 2 - (bbox_s[2] - bbox_s[0]) // 2
        draw.text((cx, footer_y + 1), seed_info, font=self._font_footer_sm, fill=_TEXT_LIGHT)

        return canvas
