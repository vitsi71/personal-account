"""Интеграционные проверки безопасности и персональных напоминаний."""

import re
import tempfile
from pathlib import Path
from uuid import uuid4
from datetime import timedelta

import pytest
from werkzeug.security import check_password_hash

from app import create_app
from database import db
from models import LoginSession, Reminder, User, utcnow
from worker import deliver_due


@pytest.fixture
def app():
    """Для каждого теста создаём независимую временную базу данных."""
    database_file = Path(tempfile.gettempdir()) / ("accounts-test-" + uuid4().hex + ".sqlite3")
    application = create_app({"TESTING": True, "SECRET_KEY": "test-only", "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(database_file)})
    yield application
    # Закрываем подключения перед удалением временной базы, в том числе на Windows.
    with application.app_context():
        db.session.remove()
        db.engine.dispose()
    database_file.unlink(missing_ok=True)


def post(client, path, data=None, token_page="/login"):
    """Отправляем форму с настоящим CSRF-токеном из страницы клиента."""
    response = client.get(token_page)
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.text)[1]
    return client.post(path, data={**(data or {}), "csrf_token": token})


def register(client, username="alice"):
    """Создаём тестовую учётную запись через публичный маршрут."""
    return post(client, "/register", {"username": username, "email": username + "@example.com", "password": "a-long-password-123"}, "/register")


def login(client, username="alice", password="a-long-password-123"):
    """Входим через форму с заданными тестовыми данными."""
    return post(client, "/login", {"username": username, "password": password})


def test_registration_login_and_revoked_cookie(app):
    """Проверяем хеширование, уникальность и отзыв даже скопированного cookie."""
    client = app.test_client()
    assert client.get("/profile").status_code == 302


    assert register(client).status_code == 302
    assert register(client).status_code == 409
    with app.app_context():
        user = db.session.scalar(db.select(User))
        assert user.password_hash != "a-long-password-123"
        assert check_password_hash(user.password_hash, "a-long-password-123")
    assert login(client, password="bad").status_code == 401
    assert login(client).status_code == 302
    assert "alice@example.com" in client.get("/profile").text
    cookie = client.get_cookie("session").value
    assert post(client, "/logout", token_page="/profile").status_code == 302
    client.set_cookie("session", cookie)
    assert client.get("/profile").status_code == 302


@pytest.mark.parametrize("due_at", ["0001-01-01T00:00:00+23:59", "9999-12-31T23:59:59-23:59"])
def test_out_of_range_utc_date_is_rejected(app, due_at):
    """Выход за диапазон UTC должен дать ошибку формы, а не сбой сервера."""
    client = app.test_client()
    register(client)
    login(client)
    response = post(client, "/reminders", {"message": "Граничная дата", "due_at": due_at}, "/profile")
    assert response.status_code == 302
    assert "выберите корректные дату и время в календаре" in client.get("/profile").text
    with app.app_context():
        assert db.session.scalar(db.select(Reminder.id)) is None


def test_ownership_xss_and_reminder_delivery(app):
    """Проверяем изоляцию аккаунтов, экранирование и однократную доставку."""
    alice, bob = app.test_client(), app.test_client()
    register(alice)
    register(bob, "bob")
    login(alice)
    login(bob, "bob")
    due = (utcnow() - timedelta(minutes=5)).isoformat() + "+00:00"
    assert post(alice, "/reminders", {"message": "<script>private</script>", "due_at": due}, "/profile").status_code == 302
    with app.app_context():
        reminder_id = db.session.scalar(db.select(Reminder.id))
    assert "private" not in bob.get("/profile").text
    assert post(bob, f"/reminders/{reminder_id}/delete", token_page="/profile").status_code == 404
    assert "&lt;script&gt;private&lt;/script&gt;" in alice.get("/profile").text
    assert deliver_due(app) == 1
    assert deliver_due(app) == 0
    assert "Уведомление доставлено" in alice.get("/profile").text
    assert post(alice, f"/reminders/{reminder_id}/delete", token_page="/profile").status_code == 302
    with app.app_context():
        assert db.session.get(Reminder, reminder_id) is None


def test_csrf_validation_and_expiration(app):
    """Проверяем защиту форм, обязательный часовой пояс и срок сессии."""
    client = app.test_client()
    assert client.post("/register", data={}).status_code == 400
    assert post(client, "/register", {"username": "x", "email": "invalid", "password": "short"}, "/register").status_code == 400
    register(client)
    login(client)
    assert client.post("/logout").status_code == 400
    post(client, "/reminders", {"message": "test", "due_at": "2026-10-11T15:00:00"}, "/profile")
    with app.app_context():
        assert db.session.scalar(db.select(Reminder.id)) is None
        record = db.session.scalar(db.select(LoginSession))
        record.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
    assert client.get("/profile").status_code == 302


def test_live_notifications_are_private_and_show_delivery(app):
    """Автообновление получает только доставленные напоминания владельца."""
    alice, bob = app.test_client(), app.test_client()
    assert alice.get("/notifications").status_code == 302
    register(alice)
    register(bob, "bob")
    login(alice)
    login(bob, "bob")
    post(alice, "/reminders", {"message": "Проверка автообновления", "due_at": "2026-01-01T00:00:00Z"}, "/profile")
    assert alice.get("/notifications").json == {"delivered_ids": []}
    deliver_due(app)
    with app.app_context():
        reminder_id = db.session.scalar(db.select(Reminder.id))
    response = alice.get("/notifications")
    assert response.json == {"delivered_ids": [reminder_id]}
    assert response.headers["Cache-Control"] == "no-store"
    assert bob.get("/notifications").json == {"delivered_ids": []}
