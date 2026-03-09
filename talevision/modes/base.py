"""Abstract base class for display modes."""
import abc
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from PIL import Image


@dataclass
class ModeState:
    """Serialisable state snapshot for a display mode."""
    mode: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


class DisplayMode(abc.ABC):
    """Abstract base for LitClock and SlowMovie modes."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique mode identifier, e.g. 'litclock' or 'slowmovie'."""

    @property
    @abc.abstractmethod
    def refresh_interval(self) -> int:
        """Seconds between renders."""

    def on_activate(self) -> None:
        """Called when this mode becomes active. Override if needed."""

    def on_deactivate(self) -> None:
        """Called when switching away from this mode. Override if needed."""

    @abc.abstractmethod
    def render(self) -> Image.Image:
        """Render and return a PIL Image (RGB, 800×480)."""

    @abc.abstractmethod
    def get_state(self) -> ModeState:
        """Return current mode state for the web dashboard."""
