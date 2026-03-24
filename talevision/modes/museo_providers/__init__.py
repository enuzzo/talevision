from .base import MuseoProvider, ArtworkInfo
from .met import MetProvider
from .cleveland import ClevelandProvider

# AIC (Art Institute of Chicago) disabled — their IIIF image server is
# behind Cloudflare JS challenge since ~March 2026, returning 403 for
# all non-browser requests.  Provider code kept in aic.py for future use.
PROVIDERS = [MetProvider(), ClevelandProvider()]

__all__ = ["MuseoProvider", "ArtworkInfo", "PROVIDERS",
           "MetProvider", "ClevelandProvider"]
