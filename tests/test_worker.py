"""Проверяем запуск планировщика в начале минуты, до опроса браузера."""
from datetime import datetime, timezone
from worker import create_scheduler


def test_delivery_is_aligned_to_start_of_minute():
    """После запуска в произвольную секунду задача должна ждать границу минуты."""
    scheduler = create_scheduler(None)
    trigger = scheduler.get_job("deliver-reminders").trigger
    now = datetime(2026, 10, 13, 10, 20, 13, tzinfo=timezone.utc)
    assert trigger.get_next_fire_time(None, now) == datetime(2026, 10, 13, 10, 21, 0, tzinfo=timezone.utc)
