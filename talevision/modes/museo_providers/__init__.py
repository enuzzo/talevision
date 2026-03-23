from .base import MuseoProvider, ArtworkInfo
from .met import MetProvider
from .aic import AICProvider
from .cleveland import ClevelandProvider

PROVIDERS = [MetProvider(), AICProvider(), ClevelandProvider()]

__all__ = ["MuseoProvider", "ArtworkInfo", "PROVIDERS",
           "MetProvider", "AICProvider", "ClevelandProvider"]
