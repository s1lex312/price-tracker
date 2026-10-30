"""Queue names and source-based routing."""

from app.models.enums import ProductSource

DEFAULT_QUEUE = "default"
PLAYWRIGHT_QUEUE = "playwright"


def queue_for_source(source: ProductSource) -> str:
    """Pick the worker queue for a product source."""
    if source == ProductSource.PLAYWRIGHT_JS:
        return PLAYWRIGHT_QUEUE
    return DEFAULT_QUEUE
