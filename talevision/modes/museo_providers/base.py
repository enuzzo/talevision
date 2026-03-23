"""Abstract base for museum data providers."""
import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class ArtworkInfo:
    title: str
    artist: str
    date: str
    department: str
    museum: str
    image_url: str
    object_url: str
    provider: str
    artwork_id: str


class MuseoProvider(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def museum_display_name(self) -> str: ...

    @abc.abstractmethod
    def fetch_catalogue_meta(self, timeout: int = 30) -> dict: ...

    @abc.abstractmethod
    def pick_random_id(self, cache_data: dict) -> str: ...

    @abc.abstractmethod
    def fetch_artwork(self, artwork_id: str, timeout: int = 10) -> Optional[ArtworkInfo]: ...
