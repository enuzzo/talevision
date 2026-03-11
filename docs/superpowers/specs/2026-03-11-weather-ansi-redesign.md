# Weather Mode ANSI Redesign

## Summary

Replace the current custom PIL weather layout with wttr.in's native ANSI terminal output, parsed and rendered character-by-character with Inconsolata Nerd Font Mono on a white background. Colours mapped from ANSI to the 7 native e-ink palette.

## Data Fetching

Endpoint: `http://wttr.in/{lat},{lon}?A&F&2&lang={lang}&{m|u}`

| Flag | Purpose |
|------|---------|
| `A` | Force ANSI colour output |
| `F` | Remove "Follow" footer |
| `2` | Current weather + 3-day forecast |
| `lang={lang}` | Localised conditions/days |
| `m` or `u` | Metric (SI) or USCS units |

Coordinates (lat/lon) used instead of city name for precision.

## ANSI Colour Mapping (e-ink 7-colour)

| ANSI code | Original | e-ink colour | RGB |
|-----------|----------|-------------|-----|
| 37 (white) | base text | Black | (0,0,0) |
| 1;37 (bold white) | emphasis | Black **Bold** | (0,0,0) |
| 33 (yellow) | temps | Orange | (255,165,0) |
| 1;33 (bold yellow) | temps emphasis | Orange **Bold** | (255,165,0) |
| 32 (green) | wind | Blue | (0,0,255) |
| 1;32 (bold green) | wind emphasis | Blue **Bold** | (0,0,255) |
| 31 (red) | alerts | Red | (255,0,0) |
| 34 (blue) | — | Blue | (0,0,255) |
| 36 (cyan) | — | Blue | (0,0,255) |
| 0 (reset) | — | Black Regular | (0,0,0) |
| 4 (underline) | — | Underline via PIL line | — |

Background: White (255,255,255). Bold: switch to Bold TTF variant.

## Rendering

- Font: InconsolataNerdFontMono Regular + Bold, 12pt
- Char cell: 6x14px
- Canvas: 800x480 white
- wttr.in output: ~125 cols x 29 rows = 750x406px
- Padding: ~25px horizontal, ~37px vertical (centred)
- Pipeline: fetch ANSI text, strip last line (location echo), parse escape codes, render char-by-char with colour/bold state, draw underlines as 1px PIL lines

## Font

InconsolataNerdFontMono (Nerd Fonts patched). 125/125 tested Unicode glyphs including arrows, weather symbols, moon phases, box drawing, block elements, braille. Regular + Bold variants.

No `d` flag in wttr.in query: keep Unicode arrows and symbols.

## Config Schema

```python
@dataclass
class WeatherConfig:
    refresh_interval: int = 600
    city: str = "Roma"
    lat: float = 41.8935
    lon: float = 12.4826
    units: str = "m"          # "m" metric, "u" USCS
    timeout: int = 10
```

## Geocoding

Switch from Nominatim to Open-Meteo free geocoding API (same as ScryBar):
`https://geocoding-api.open-meteo.com/v1/search?count=6&language={lang}&name={query}`

Returns city name + lat/lon. No API key required.

## API Endpoints

- `GET /api/weather/location` — returns `{city, lat, lon}`
- `POST /api/weather/location` — accepts `{city, lat, lon}`
- `GET /api/weather/search?q=...` — Open-Meteo geocoding, returns `[{name, display, lat, lon}]`
- `GET /api/weather/units` — returns `{units}`
- `POST /api/weather/units` — accepts `{units: "m"|"u"}`

## Frontend

- City autocomplete (existing pattern, now stores lat/lon)
- Metric/Imperial toggle
- Language selector (shared with LitClock/Wikipedia)
