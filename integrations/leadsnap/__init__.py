"""LeadSnap Heatmaps API integration — zero-dependency, stdlib-only client.

See README.md for usage and THREAT_MODEL.md for data boundaries.
"""

from .client import (
    DEFAULT_BASE_URL,
    TOKEN_ENV_VAR,
    LeadSnapAuthError,
    LeadSnapClient,
    LeadSnapError,
    Page,
)

__all__ = [
    "LeadSnapClient",
    "LeadSnapError",
    "LeadSnapAuthError",
    "Page",
    "DEFAULT_BASE_URL",
    "TOKEN_ENV_VAR",
]
