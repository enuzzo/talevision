from .base import MuseoProvider, ArtworkInfo
from .met import MetProvider
from .cleveland import ClevelandProvider
from .vanda import VandAProvider
from .smithsonian import SmithsonianProvider


def build_providers(smithsonian_api_key: str = "") -> list:
    providers = [MetProvider(), ClevelandProvider(), VandAProvider()]
    if smithsonian_api_key:
        providers.append(SmithsonianProvider(api_key=smithsonian_api_key))
    return providers


__all__ = ["MuseoProvider", "ArtworkInfo", "build_providers",
           "MetProvider", "ClevelandProvider", "VandAProvider",
           "SmithsonianProvider"]
