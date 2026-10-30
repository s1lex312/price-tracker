"""Smoke checks for the Celery application wiring."""

from app.models.enums import ProductSource
from app.scheduler.celery_app import celery_app
from app.scheduler.queues import queue_for_source


def test_celery_beat_schedule_configured() -> None:
    schedule = celery_app.conf.beat_schedule

    assert "price-check" in schedule
    entry = schedule["price-check"]
    assert entry["task"] == "app.scheduler.celery_app.dispatch_price_check_task"
    assert entry["schedule"] > 0


def test_tasks_registered() -> None:
    assert "dispatch_price_check" in celery_app.tasks
    assert "refresh_product" in celery_app.tasks


def test_default_queue_configured() -> None:
    assert celery_app.conf.task_default_queue == "default"


def test_queue_routing() -> None:
    assert queue_for_source(ProductSource.PLAYWRIGHT_JS) == "playwright"
    assert queue_for_source(ProductSource.BOOKS_TOSCRAPE) == "default"
    assert queue_for_source(ProductSource.COINGECKO) == "default"
