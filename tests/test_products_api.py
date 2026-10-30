"""Tests for the products REST API."""

import uuid
from decimal import Decimal

import httpx
import respx

BOOK_URL = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
HTML_OK = "<html><body><p class='price_color'>&pound;51.77</p></body></html>"

PRODUCT_PAYLOAD = {
    "name": "A Light in the Attic",
    "source": "books_toscrape",
    "external_id": BOOK_URL,
    "target_price": "60.00",
    "user_telegram_id": 123456,
}

COINGECKO_PAYLOAD = {
    "name": "Bitcoin",
    "source": "coingecko",
    "external_id": "bitcoin",
    "target_price": "100000",
    "user_telegram_id": 123456,
}


async def test_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["scheduler"] == "stopped"  # lifespan is off under ASGITransport


async def test_create_product(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/products", json=PRODUCT_PAYLOAD)

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == PRODUCT_PAYLOAD["name"]
    assert data["currency"] == "GBP"  # default from the parser
    assert data["current_price"] is None
    assert data["is_active"] is True


async def test_create_product_invalid_external_id(
    client: httpx.AsyncClient,
) -> None:
    payload = {**PRODUCT_PAYLOAD, "external_id": "https://ozon.ru/product/1"}
    resp = await client.post("/api/v1/products", json=payload)

    assert resp.status_code == 422


async def test_create_coingecko_defaults_to_usd(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.post("/api/v1/products", json=COINGECKO_PAYLOAD)

    assert resp.status_code == 201
    assert resp.json()["currency"] == "USD"


async def test_get_product_not_found(client: httpx.AsyncClient) -> None:
    missing_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/products/{missing_id}")

    assert resp.status_code == 404
    assert resp.json() == {"detail": f"Product {missing_id} not found"}


async def test_list_products(client: httpx.AsyncClient) -> None:
    await client.post("/api/v1/products", json=PRODUCT_PAYLOAD)
    await client.post("/api/v1/products", json=COINGECKO_PAYLOAD)

    resp = await client.get("/api/v1/products")

    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_delete_product(client: httpx.AsyncClient) -> None:
    created = await client.post("/api/v1/products", json=PRODUCT_PAYLOAD)
    product_id = created.json()["id"]

    resp = await client.delete(f"/api/v1/products/{product_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/products/{product_id}")
    assert resp.status_code == 404


@respx.mock
async def test_refresh_updates_price_and_history(
    client: httpx.AsyncClient,
) -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))
    created = await client.post("/api/v1/products", json=PRODUCT_PAYLOAD)
    product_id = created.json()["id"]

    resp = await client.post(f"/api/v1/products/{product_id}/refresh")

    assert resp.status_code == 200
    # In-memory Decimal is not quantized to the DB scale (18, 8)
    assert Decimal(resp.json()["current_price"]) == Decimal("51.77")

    history = await client.get(f"/api/v1/products/{product_id}/history")
    assert history.status_code == 200
    points = history.json()
    assert len(points) == 1
    assert points[0]["price"] == "51.77000000"


@respx.mock
async def test_history_respects_limit(client: httpx.AsyncClient) -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))
    created = await client.post("/api/v1/products", json=PRODUCT_PAYLOAD)
    product_id = created.json()["id"]
    for _ in range(3):
        await client.post(f"/api/v1/products/{product_id}/refresh")

    history = await client.get(
        f"/api/v1/products/{product_id}/history", params={"limit": 2}
    )

    assert len(history.json()) == 2


@respx.mock
async def test_refresh_parser_error_returns_502_and_stores_error(
    client: httpx.AsyncClient,
) -> None:
    respx.get(BOOK_URL).mock(
        return_value=httpx.Response(200, text="<html><body></body></html>")
    )
    created = await client.post("/api/v1/products", json=PRODUCT_PAYLOAD)
    product_id = created.json()["id"]

    resp = await client.post(f"/api/v1/products/{product_id}/refresh")

    assert resp.status_code == 502
    assert "detail" in resp.json()

    product = await client.get(f"/api/v1/products/{product_id}")
    assert product.json()["last_error"] is not None
    assert product.json()["current_price"] is None
