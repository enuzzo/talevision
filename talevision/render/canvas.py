"""InkyCanvas — hardware display wrapper with simulation fallback.

On Raspberry Pi with Inky installed: sends RGB image to e-ink display.
On other hardware (macOS/Linux dev): saves PNG to disk for preview.
"""
import logging
import warnings
from pathlib import Path
from typing import Optional

from PIL import Image

from talevision.config.schema import DisplayConfig

log = logging.getLogger(__name__)

try:
    from inky.inky_ac073tc1a import Inky as InkyImpression7
    warnings.filterwarnings("ignore", message="Busy Wait: Held high.*")
    INKY_AVAILABLE = True
except ImportError:
    INKY_AVAILABLE = False
except Exception as exc:
    INKY_AVAILABLE = False
    log.warning(f"Inky import error: {exc}")


class InkyCanvas:
    """Wraps the Inky e-ink display.

    Falls back to saving PNG to disk when not running on Pi hardware.
    """

    def __init__(
        self,
        display_config: DisplayConfig,
        sim_output_path: Optional[Path] = None,
    ):
        self._cfg = display_config
        self._sim_path = sim_output_path or Path("talevision_frame.png")
        self._display = None
        self._init_display()

    def _init_display(self) -> None:
        if not INKY_AVAILABLE:
            log.info("Inky library not available — running in simulation mode")
            return
        try:
            self._display = InkyImpression7(
                resolution=(self._cfg.width, self._cfg.height),
            )
            log.info(
                f"Inky display initialized: {self._display.__class__.__name__} "
                f"{self._display.resolution[0]}x{self._display.resolution[1]}"
            )
        except Exception as exc:
            log.warning(f"Inky display init failed: {exc}. Simulation mode active.")
            self._display = None

    @property
    def width(self) -> int:
        return self._cfg.width

    @property
    def height(self) -> int:
        return self._cfg.height

    def show(self, image: Image.Image, saturation: Optional[float] = None) -> None:
        """Display image on Inky or save PNG for simulation.

        Args:
            image: PIL Image in RGB mode.
            saturation: Override display saturation (default: from config).
        """
        sat = saturation if saturation is not None else self._cfg.saturation

        # Ensure RGB
        if image.mode != "RGB":
            image = image.convert("RGB")

        if self._display is not None:
            try:
                self._display.set_image(image, saturation=sat)
                self._display.show()
                log.info("Image sent to Inky display")
            except Exception as exc:
                log.error(f"Inky display error: {exc}")
        else:
            try:
                image.save(str(self._sim_path), format="PNG")
                log.info(f"Simulation: frame saved to {self._sim_path}")
            except Exception as exc:
                log.error(f"Failed to save simulation frame: {exc}")
