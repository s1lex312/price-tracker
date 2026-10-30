"""Parser for JS-rendered sites via headless Chromium (Playwright)."""

from decimal import Decimal

from app.models.enums import ProductSource
from app.parsers.base import (
    BaseParser,
    ParserError,
    ParserNetworkError,
    ParserStructureError,
    extract_price,
)


class PlaywrightParser(BaseParser):
    """Renders a page in headless Chromium and reads a CSS selector.

    Generic by design: works with any page URL + CSS selector pair.
    The currency cannot be derived from an arbitrary page, so products
    of this source must set it explicitly.
    """

    source = ProductSource.PLAYWRIGHT_JS
    currency = None  # unknown upfront; required in ProductCreate

    async def fetch_price(
        self, external_id: str, *, selector: str | None = None
    ) -> Decimal:
        """Render ``external_id`` and read the price from ``selector``."""
        if not selector:
            raise ParserStructureError(
                "price_selector is required for source playwright_js"
            )
        try:
            from playwright.async_api import TimeoutError as PWTimeout
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ParserError(
                "playwright extra is not installed "
                "(pip install 'price-tracker[playwright]' + "
                "playwright install chromium)"
            ) from exc

        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                page = await browser.new_page()
                try:
                    await page.goto(
                        external_id,
                        timeout=self._timeout * 1000,
                        wait_until="domcontentloaded",
                    )
                except PWTimeout as exc:
                    raise ParserNetworkError(f"Timeout loading {external_id}") from exc
                element = await page.query_selector(selector)
                if element is None:
                    raise ParserStructureError(
                        f"Selector {selector!r} not found at {external_id}"
                    )
                text = await element.inner_text()
            finally:
                await browser.close()

        return extract_price(text)
