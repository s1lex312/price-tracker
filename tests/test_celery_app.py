"""Smoke checks for the Celery application wiring."""

from app.scheduler.celery_app import celery_app, price_check_task


def test_celery_beat_schedule_configured() -> None:
    schedule = celery_app.conf.beat_schedule

    assert "price-check" in schedule
    entry = schedule["price-check"]
    assert entry["task"] == "app.scheduler.celery_app.price_check_task"
    assert entry["schedule"] > 0


def test_price_check_task_registered() -> None:
    assert price_check_task.name == "price_check"
    assert "price_check" in celery_app.tasks
