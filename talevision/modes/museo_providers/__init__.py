from .base import MuseoProvider, ArtworkInfo
from .met import MetProvider
from .cleveland import ClevelandProvider
from .vanda import VandAProvider

PROVIDERS = [MetProvider(), ClevelandProvider(), VandAProvider()]

__all__ = ["MuseoProvider", "ArtworkInfo", "PROVIDERS",
           "MetProvider", "ClevelandProvider", "VandAProvider"]
