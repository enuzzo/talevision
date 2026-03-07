#!/usr/bin/env python3
"""
generate_sidecars.py
Scansiona la cartella media/, cerca ogni film su TMDB e genera i .json sidecar.
Netmilk Studio — 2026

Usage:
  python generate_sidecars.py                    # usa media/ nella cartella corrente
  python generate_sidecars.py --media /path/to   # cartella custom
  python generate_sidecars.py --dry-run          # mostra senza scrivere
"""
import argparse
import json
import re
import sys
import urllib.request
import urllib.parse
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.prompt import Confirm
    from rich.panel import Panel
    console = Console()
except ImportError:
    print("Install rich: pip install rich")
    sys.exit(1)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".m4v"}
TMDB_BASE = "https://api.themoviedb.org/3"


def load_api_key(secrets_path: Path) -> str:
    """Load TMDB API key from secrets.yaml."""
    try:
        import yaml
        with open(secrets_path) as f:
            data = yaml.safe_load(f) or {}
        key = data.get("tmdb_api_key", "")
        if key:
            return key
    except ImportError:
        # No PyYAML — parse manually (it's a simple key: value file)
        pass
    except FileNotFoundError:
        pass

    # Manual parse fallback
    try:
        for line in secrets_path.read_text().splitlines():
            if "tmdb_api_key" in line:
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass

    return ""


def parse_filename(filename: str) -> tuple[str, str]:
    """Extract title and year from filename patterns like:
      'Koyaanisqatsi - 1982__slowmovie.mp4'
      'Pulp Fiction - 1994_eink.mp4'
      'The Conformist - 1970.mp4'
    Returns (title, year).
    """
    stem = Path(filename).stem
    # Strip suffixes like __slowmovie, _eink, _slowmovie
    stem = re.sub(r'[_]+[a-z]+$', '', stem, flags=re.IGNORECASE)
    stem = re.sub(r'[_]+[a-z]+$', '', stem, flags=re.IGNORECASE)  # double pass
    stem = stem.strip('_ ')

    # Pattern: "Title - YEAR"
    m = re.match(r'^(.+?)\s*-\s*(\d{4})\s*$', stem)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Pattern: "Title (YEAR)"
    m = re.match(r'^(.+?)\s*\((\d{4})\)\s*$', stem)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # No year found
    return stem.strip(), ""


def tmdb_search(title: str, year: str, api_key: str) -> dict | None:
    """Search TMDB for a movie. Returns best match or None."""
    params = {
        "api_key": api_key,
        "query": title,
        "language": "en-US",
    }
    if year:
        params["year"] = year

    url = f"{TMDB_BASE}/search/movie?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
        if not results:
            return None
        return results[0]
    except Exception as exc:
        console.print(f"[red]TMDB error for '{title}': {exc}[/red]")
        return None


def tmdb_get_credits(movie_id: int, api_key: str) -> str:
    """Fetch director name from TMDB credits."""
    url = f"{TMDB_BASE}/movie/{movie_id}/credits?api_key={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        crew = data.get("crew", [])
        directors = [p["name"] for p in crew if p.get("job") == "Director"]
        return ", ".join(directors) if directors else "N/A"
    except Exception:
        return "N/A"


def build_sidecar(video_path: Path, api_key: str) -> dict | None:
    """Search TMDB and build sidecar dict for a video file."""
    title, year = parse_filename(video_path.name)
    console.print(f"  Searching: [cyan]{title}[/cyan] ({year or '?'}) ...", end=" ")

    result = tmdb_search(title, year, api_key)
    if not result:
        # Retry without year
        if year:
            result = tmdb_search(title, "", api_key)
    if not result:
        console.print("[red]not found[/red]")
        return {"title": title, "year": year or "N/A", "director": "N/A"}

    movie_id = result["id"]
    found_title = result.get("title", title)
    found_year = (result.get("release_date") or "")[:4] or year or "N/A"
    director = tmdb_get_credits(movie_id, api_key)
    imdb_url = f"https://www.themoviedb.org/movie/{movie_id}"

    console.print(f"[green]✓[/green] {found_title} ({found_year}) — {director}")

    return {
        "title": found_title,
        "year": found_year,
        "director": director,
        "tmdb_id": movie_id,
        "imdb_url": imdb_url,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate TMDB sidecar .json files for SlowMovie")
    parser.add_argument("--media", default="media", help="Path to media folder")
    parser.add_argument("--secrets", default="secrets.yaml", help="Path to secrets.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Show results without writing files")
    args = parser.parse_args()

    media_dir = Path(args.media)
    secrets_path = Path(args.secrets)

    console.print(Panel.fit(
        "[bold white]🎬 generate_sidecars[/bold white]\n"
        "[dim]Fetch movie metadata from TMDB and write .json sidecar files[/dim]",
        border_style="cyan"
    ))

    # Load API key
    api_key = load_api_key(secrets_path)
    if not api_key:
        console.print(f"[red]TMDB API key not found in {secrets_path}[/red]")
        console.print("Add 'tmdb_api_key: YOUR_KEY' to secrets.yaml")
        sys.exit(1)

    # Find videos
    if not media_dir.is_dir():
        console.print(f"[red]Media folder not found: {media_dir}[/red]")
        sys.exit(1)

    videos = sorted([f for f in media_dir.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS])
    if not videos:
        console.print("[yellow]No video files found.[/yellow]")
        sys.exit(0)

    # Check which already have sidecars
    missing = [v for v in videos if not v.with_suffix(".json").exists()]
    existing = [v for v in videos if v.with_suffix(".json").exists()]

    console.print(f"\n[dim]Found {len(videos)} video(s) in {media_dir}[/dim]")
    if existing:
        console.print(f"[dim]{len(existing)} already have .json sidecars — skipping[/dim]")
    if not missing:
        console.print("[green]All videos already have sidecar files![/green]")
        sys.exit(0)

    console.print(f"\n[cyan]Fetching metadata for {len(missing)} video(s):[/cyan]\n")

    results = []
    for video in missing:
        sidecar = build_sidecar(video, api_key)
        if sidecar:
            results.append((video, sidecar))

    if not results:
        console.print("\n[red]No metadata found.[/red]")
        sys.exit(1)

    # Summary table
    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("File")
    table.add_column("Title")
    table.add_column("Year")
    table.add_column("Director")
    for video, data in results:
        table.add_row(video.name, data["title"], data.get("year", ""), data.get("director", ""))

    console.print()
    console.print(table)

    if args.dry_run:
        console.print("\n[yellow]Dry run — no files written.[/yellow]")
        sys.exit(0)

    if not Confirm.ask(f"\nWrite {len(results)} .json sidecar file(s)?", default=True):
        console.print("[yellow]Cancelled.[/yellow]")
        sys.exit(0)

    for video, data in results:
        out = video.with_suffix(".json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        console.print(f"  [green]✓[/green] {out.name}")

    console.print(f"\n[bold green]{len(results)} sidecar file(s) written.[/bold green]")


if __name__ == "__main__":
    main()
