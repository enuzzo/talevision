"""Flora mode — generative botanical art via L-system grammars."""
import math
import random
import logging
from datetime import date
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
_ACCENT      = (37, 99, 235)

_STEM_DARK   = (28, 88, 18)
_STEM_MID    = (44, 128, 34)
_STEM_LIGHT  = (68, 162, 52)
_LEAF_GREEN  = (88, 168, 62)

_FLWR_RED    = (186, 34, 34)
_FLWR_ORANGE = (206, 106, 18)
_FLWR_YELLOW = (194, 168, 16)
_FLWR_PINK   = (196, 78, 116)
_FLWR_BLUE   = (38, 96, 188)

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
        "flower_color": _FLWR_PINK, "flower_prob": 0.25,
    },
    {
        "id": "vine",
        "genera":   ["Hedera", "Parthenocissus", "Vitis", "Wisteria"],
        "epithets": ["helix", "quinquefolia", "vinifera", "sinensis"],
        "family": "Araliaceae", "order": "Apiales",
        "axiom": "X",
        "rules": {"X": "F-[[X]+X]+F[+FX]-X", "F": "FF"},
        "angle": 22.0, "iterations": 5,
        "flower_color": _FLWR_BLUE, "flower_prob": 0.12,
    },
    {
        "id": "flower",
        "genera":   ["Rosa", "Hibiscus", "Papaver", "Magnolia"],
        "epithets": ["canina", "sabdariffa", "rhoeas", "grandiflora"],
        "family": "Rosaceae", "order": "Rosales",
        "axiom": "F",
        "rules": {"F": "F[+F][-F][++F][--F]F"},
        "angle": 36.0, "iterations": 3,
        "flower_color": _FLWR_RED, "flower_prob": 0.35,
    },
    {
        "id": "bamboo",
        "genera":   ["Phyllostachys", "Bambusa", "Fargesia", "Dendrocalamus"],
        "epithets": ["aurea", "vulgaris", "murielae", "giganteus"],
        "family": "Poaceae", "order": "Poales",
        "axiom": "A",
        "rules": {"A": "FFF[++FF][--FF]A"},
        "angle": 30.0, "iterations": 5,
        "flower_color": _FLWR_YELLOW, "flower_prob": 0.06,
    },
    {
        "id": "reed",
        "genera":   ["Phragmites", "Arundo", "Typha", "Calamagrostis"],
        "epithets": ["australis", "donax", "latifolia", "epigejos"],
        "family": "Poaceae", "order": "Poales",
        "axiom": "F",
        "rules": {"F": "FF[+F][-F]"},
        "angle": 18.0, "iterations": 5,
        "flower_color": _FLWR_ORANGE, "flower_prob": 0.15,
    },
    {
        "id": "spring",
        "genera":   ["Narcissus", "Galanthus", "Hyacinthus", "Tulipa"],
        "epithets": ["poeticus", "nivalis", "orientalis", "sylvestris"],
        "family": "Amaryllidaceae", "order": "Asparagales",
        "axiom": "X",
        "rules": {"X": "F[+X]F[-X]+X", "F": "FF"},
        "angle": 20.0, "iterations": 5,
        "flower_color": _FLWR_YELLOW, "flower_prob": 0.22,
    },
]

_MAX_STR_LEN = 80_000
_PLANT_PANEL_W = 500
_FOOTER_H = 40
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

    for cmd in s:
        if cmd == "F":
            nx = x + step * math.cos(math.radians(direction))
            ny = y + step * math.sin(math.radians(direction))
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
            old_x, old_y = x, y
            x, y, direction, depth = stack.pop()
            fc = species.get("flower_color")
            if fc and rng.random() < species.get("flower_prob", 0.0):
                r = max(2, 5 - depth)
                draw.ellipse([(old_x - r, old_y - r), (old_x + r, old_y + r)], fill=fc)


class FloraMode(DisplayMode):

    def __init__(self, config: AppConfig, base_dir: Path = Path(".")):
        self._cfg = config.flora
        self._display = config.display
        self._base_dir = base_dir

        fonts = base_dir / "assets" / "fonts"
        self._font_specimen  = _load_font(fonts / "Signika-Regular.ttf", 15)
        self._font_genus     = _load_font(fonts / "Lobster-Regular.ttf", 34)
        self._font_epithet   = _load_font(fonts / "Taviraj-Italic.ttf", 20)
        self._font_detail    = _load_font(fonts / "Taviraj-Regular.ttf", 14)
        self._font_footer    = _load_font(fonts / "Signika-Bold.ttf", 16)
        self._font_footer_sm = _load_font(fonts / "InconsolataNerdFontMono-Bold.ttf", 13)

        self._last_species_id = ""
        self._last_genus = ""
        self._last_epithet = ""
        self._cache_path = base_dir / "cache" / "flora_frame.png"

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
        rng = random.Random(today.isoformat())

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

        return img

    def get_state(self) -> ModeState:
        return ModeState(mode="flora", extra={
            "species": self._last_species_id,
            "genus": self._last_genus,
            "epithet": self._last_epithet,
        })

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

        y = 32

        # "Specimen #XXXX"
        specimen_str = f"Specimen  #{specimen_num:04d}"
        draw.text((lx, y), specimen_str, font=self._font_specimen, fill=_TEXT_LIGHT)
        y += 32

        # Genus name (Lobster, large)
        genus_text = genus
        bbox = draw.textbbox((0, 0), genus_text, font=self._font_genus)
        if (bbox[2] - bbox[0]) > label_inner_w:
            genus_text = genus_text[:10] + "…"
        draw.text((lx, y), genus_text, font=self._font_genus, fill=_TEXT_NAVY)
        y += (bbox[3] - bbox[1]) + 6

        # Epithet (italic)
        draw.text((lx, y), epithet, font=self._font_epithet, fill=_TEXT_GRAY)
        y += 28

        # Thin separator
        y += 6
        draw.line([(lx, y), (lx + min(label_inner_w, 200), y)], fill=_SEP_LINE, width=1)
        y += 12

        # Family / Order
        draw.text((lx, y), f"Fam.  {species['family']}", font=self._font_detail, fill=_TEXT_GRAY)
        y += 20
        draw.text((lx, y), f"Ord.  {species['order']}", font=self._font_detail, fill=_TEXT_GRAY)
        y += 36

        # Observation date
        try:
            from babel.dates import format_date
            date_str = format_date(today, "d MMMM yyyy", locale="en")
        except Exception:
            date_str = today.strftime("%d %B %Y")

        draw.text((lx, y), "Observed", font=self._font_detail, fill=_TEXT_LIGHT)
        y += 18
        draw.text((lx, y), date_str, font=self._font_detail, fill=_TEXT_NAVY)
        y += 22

        # Location
        draw.text((lx, y), self._cfg.location, font=self._font_detail, fill=_TEXT_GRAY)

        # ── Footer bar ────────────────────────────────────────────────────────
        draw.rectangle([(0, h - _FOOTER_H), (w, h)], fill=_DARK_NAVY)

        draw.text(
            (_MARGIN, h - _FOOTER_H + 11),
            "FLORA",
            font=self._font_footer,
            fill=(255, 255, 255),
        )

        seed_info = f"Seed: {today.strftime('%Y%m%d')}  ·  L-Sys {species['id']}  ·  iter {species['iterations']}"
        bbox_info = draw.textbbox((0, 0), seed_info, font=self._font_footer_sm)
        info_w = bbox_info[2] - bbox_info[0]
        draw.text(
            (w - info_w - _MARGIN, h - _FOOTER_H + 12),
            seed_info,
            font=self._font_footer_sm,
            fill=_TEXT_LIGHT,
        )

        return canvas
