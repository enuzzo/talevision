from .base import MuseoProvider, ArtworkInfo
from .met import MetProvider
from .cleveland import ClevelandProvider
from .harvard import HarvardProvider
from .smithsonian import SmithsonianProvider


def build_providers(harvard_api_key: str = "", smithsonian_api_key: str = "") -> list:
    providers = [MetProvider(), ClevelandProvider()]
    if harvard_api_key:
        providers.append(HarvardProvider(api_key=harvard_api_key))
    if smithsonian_api_key:
        providers.append(SmithsonianProvider(api_key=smithsonian_api_key))
    return providers


__all__ = ["MuseoProvider", "ArtworkInfo", "build_providers",
           "MetProvider", "ClevelandProvider", "HarvardProvider",
           "SmithsonianProvider"]
