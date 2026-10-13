"""Отдельный процесс планировщика: запуск командой python worker.py."""
from apscheduler.schedulers.blocking import BlockingScheduler
from app import create_app
from database import db
from models import LoginSession, Reminder, utcnow


def deliver_due(app):
    """Публикуем наступившие уведомления и удаляем просроченные сессии."""
    with app.app_context():
        now = utcnow()
        # Доставка означает публикацию в уведомлениях личного кабинета владельца.
        # Атомарное обновление предотвращает повторную доставку и обрабатывает
        # все просроченные напоминания, включая накопившиеся за время простоя.
        result = db.session.execute(db.update(Reminder).where(Reminder.delivered_at.is_(None), Reminder.due_at <= now).values(delivered_at=now))
        db.session.execute(db.delete(LoginSession).where(LoginSession.expires_at <= now))
        db.session.commit()
        return result.rowcount


def create_scheduler(app):
    """Проверяем сроки на нулевой секунде минуты, до браузерного опроса на :02."""
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(deliver_due, "cron", second=0, args=[app], id="deliver-reminders",
                      max_instances=1, coalesce=True, misfire_grace_time=60)
    return scheduler


if __name__ == "__main__":
    app = create_app()
    # При перезапуске сразу обрабатываем напоминания, накопившиеся за время простоя.
    deliver_due(app)
    scheduler = create_scheduler(app)
    print("Планировщик запущен. Проверка в начале каждой минуты (:00). Ctrl+C — остановка.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
