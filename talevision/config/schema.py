"""Dataclass schema for TaleVision configuration."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DisplayConfig:
    width: int = 800
    height: int = 480
    saturation: float = 0.6


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: Optional[str] = None
    max_bytes: int = 10485760
    backup_count: int = 3


@dataclass
class SuspendConfig:
    enabled: bool = True
    start: str = "23:00"
    end: str = "07:00"
    days: List[int] = field(default_factory=lambda: list(range(7)))
    message: str = "TaleVision — Netmilk Studio"
    logo_path: str = "assets/icons/logo.png"


@dataclass
class FontEntryConfig:
    file: str = ""
    size: int = 20
    max_width: int = 700


@dataclass
class FontsConfig:
    dir: str = "assets/fonts"
    header: FontEntryConfig = field(default_factory=lambda: FontEntryConfig(file="Signika-Bold.ttf", size=32))
    quote: FontEntryConfig = field(default_factory=lambda: FontEntryConfig(file="Taviraj-Regular.ttf", size=28, max_width=700))
    quote_italic: FontEntryConfig = field(default_factory=lambda: FontEntryConfig(file="Taviraj-Italic.ttf", size=28, max_width=700))
    author: FontEntryConfig = field(default_factory=lambda: FontEntryConfig(file="Taviraj-Italic.ttf", size=22, max_width=700))
    title: FontEntryConfig = field(default_factory=lambda: FontEntryConfig(file="Taviraj-Regular.ttf", size=22, max_width=700))
    fallback: FontEntryConfig = field(default_factory=lambda: FontEntryConfig(file="Taviraj-Regular.ttf", size=26, max_width=700))


@dataclass
class LitClockHeaderConfig:
    show: bool = True
    babel_locale: str = "it"
    babel_format: str = "HH:mm '–' EEEE d MMMM y"
    separator_line: bool = True
    separator_line_thickness: int = 2
    separator_line_spacing: int = 10
    header_bottom_spacing: int = 20


@dataclass
class LitClockConfig:
    refresh_rate: int = 60
    data_dir: str = "assets/lang"
    language: str = "it"
    use_italic_for_em: bool = True
    invert_colors: bool = False
    vertical_centering_adjustment: int = 40
    header: LitClockHeaderConfig = field(default_factory=LitClockHeaderConfig)
    text_block_padding: int = 10
    intra_line_spacing: int = 6
    block_separator_spacing: int = 30
    fonts: FontsConfig = field(default_factory=FontsConfig)


@dataclass
class FrameSelectionConfig:
    skip_start_seconds: int = 30
    skip_end_seconds: int = 120


@dataclass
class ImageConfig:
    fit_mode: str = "cover"
    brightness: float = 1.1
    contrast: float = 1.2
    color: float = 1.3
    gamma: float = 1.3
    use_autocontrast: bool = False


@dataclass
class OverlayConfig:
    show_info: bool = True
    qr_enabled: bool = True
    qr_content: str = "imdb_search"
    qr_size: int = 70
    font_size: int = 22
    bottom_margin: int = 35


@dataclass
class SlowMovieFontsConfig:
    dir: str = "assets/fonts"
    bold: str = "Signika-Bold.ttf"
    light: str = "Signika-Light.ttf"


@dataclass
class SlowMovieConfig:
    refresh_interval: int = 90
    media_dir: str = "media"
    video_file: str = "random"
    cache_file: str = "cache/video_info_cache.json"
    frame_selection: FrameSelectionConfig = field(default_factory=FrameSelectionConfig)
    image: ImageConfig = field(default_factory=ImageConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    fonts: SlowMovieFontsConfig = field(default_factory=SlowMovieFontsConfig)


@dataclass
class AnsiConfig:
    refresh_interval: int = 180          # 3 minutes
    art_dir: str = "assets/ansi"
    order: str = "sequential"            # sequential | random


@dataclass
class WikipediaConfig:
    refresh_interval: int = 300
    language: str = "it"
    languages: List[str] = field(default_factory=lambda: ["it", "es", "pt", "en", "fr", "de"])
    timeout: int = 10


@dataclass
class WeatherConfig:
    refresh_interval: int = 600
    city: str = "Roma"
    lat: float = 41.8935
    lon: float = 12.4826
    units: str = "m"
    language: str = "it"
    timeout: int = 10


@dataclass
class MuseoFontsConfig:
    dir: str = "assets/fonts"
    bold: str = "Signika-Bold.ttf"
    light: str = "Signika-Light.ttf"
    mono: str = "InconsolataNerdFontMono-Regular.ttf"


@dataclass
class MuseoConfig:
    refresh_interval: int = 300
    timeout: int = 60
    cache_max_age: int = 86400
    brightness: float = 1.1
    contrast: float = 1.2
    color: float = 1.3

    overlay: OverlayConfig = field(default_factory=lambda: OverlayConfig(
        qr_content="museo_page",
    ))
    fonts: MuseoFontsConfig = field(default_factory=MuseoFontsConfig)


@dataclass
class KoanConfig:
    refresh_interval: int = 900
    archive_dir: str = "cache/koan_archive"
    seed_data: str = "assets/data/koan_seeds.json"
    language: str = "it"


@dataclass
class ButtonsConfig:
    enabled: bool = True
    gpio_map: dict = field(default_factory=lambda: {"a": 5, "b": 6, "c": 16, "d": 24})
    actions: dict = field(default_factory=lambda: {"a": "switch_mode", "b": "force_refresh", "c": "toggle_suspend", "d": None})


@dataclass
class AppSectionConfig:
    default_mode: str = "litclock"


@dataclass
class AppConfig:
    app: AppSectionConfig = field(default_factory=AppSectionConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    web: WebConfig = field(default_factory=WebConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    suspend: SuspendConfig = field(default_factory=SuspendConfig)
    litclock: LitClockConfig = field(default_factory=LitClockConfig)
    slowmovie: SlowMovieConfig = field(default_factory=SlowMovieConfig)
    ansi: AnsiConfig = field(default_factory=AnsiConfig)
    wikipedia: WikipediaConfig = field(default_factory=WikipediaConfig)
    weather: WeatherConfig = field(default_factory=WeatherConfig)
    museo: MuseoConfig = field(default_factory=MuseoConfig)
    koan: KoanConfig = field(default_factory=KoanConfig)
    buttons: ButtonsConfig = field(default_factory=ButtonsConfig)
