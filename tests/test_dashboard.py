"""Smoke tests for the server-rendered dashboard."""

import httpx
import respx

from tests.test_products_api import BOOK_URL, HTML_OK, PRODUCT_PAYLOAD


async def test_index_renders_empty(client: httpx.AsyncClient) -> None:
    resp = await client.get("/")

    assert resp.status_code == 200
    assert "Добавить товар" in resp.text
    assert "Пока пусто" in resp.text


async def test_create_via_form(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/products",
        data={
            "name": "A Light in the Attic",
            "source": "books_toscrape",
            "external_id": BOOK_URL,
            "target_price": "60.00",
            "currency": "",
            "user_telegram_id": "123456",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "A Light in the Attic" in resp.text


async def test_create_via_form_invalid_external_id(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.post(
        "/products",
        data={
            "name": "Bad",
            "source": "books_toscrape",
            "external_id": "https://ozon.ru/product/1",
            "target_price": "10",
            "currency": "",
            "user_telegram_id": "123456",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "banner-error" in resp.text


@respx.mock
async def test_product_page_refresh_and_delete(
    client: httpx.AsyncClient,
) -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))
    created = await client.post("/api/v1/products", json=PRODUCT_PAYLOAD)
    product_id = created.json()["id"]

    page = await client.get(f"/products/{product_id}")
    assert page.status_code == 200
    assert PRODUCT_PAYLOAD["name"] in page.text

    refreshed = await client.post(
        f"/products/{product_id}/refresh", follow_redirects=True
    )
    assert refreshed.status_code == 200
    assert "51.77" in refreshed.text
    assert "priceChart" in refreshed.text

    updated = await client.post(
        f"/products/{product_id}/target-price",
        data={"target_price": "42.50"},
        follow_redirects=True,
    )
    assert updated.status_code == 200
    assert "42.5" in updated.text

    deleted = await client.post(f"/products/{product_id}/delete", follow_redirects=True)
    assert deleted.status_code == 200
    # NB: the product name also lives in the add-form placeholder,
    # so check the row link instead
    assert f"/products/{product_id}" not in deleted.text


async def test_product_page_missing_redirects_home(
    client: httpx.AsyncClient,
) -> None:
    import uuid

    resp = await client.get(f"/products/{uuid.uuid4()}", follow_redirects=True)
    assert resp.status_code == 200
    assert "Добавить товар" in resp.text
