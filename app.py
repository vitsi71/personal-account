"""Создание Flask-приложения и защищённые маршруты личного кабинета."""

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event

from auth import bp, load_user, login_required
from database import db
from models import Reminder


def create_app(test_config=None):
    """Настраиваем базу, защиту форм и маршруты; тесты используют свою SQLite."""
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    secret = os.environ.get("SECRET_KEY")
    if not secret and not test_config:
        # Сохраняем секрет между перезапусками, не включая его в исходный код.
        secret_file = Path(app.instance_path) / "secret.key"
        try:
            with secret_file.open("x", encoding="utf-8") as stream:
                stream.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        secret = secret_file.read_text(encoding="utf-8").strip()
    app.config.from_mapping(
        SECRET_KEY=secret,
        SQLALCHEMY_DATABASE_URI="sqlite:///accounts.sqlite3",
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"timeout": 30}},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    CSRFProtect(app)
    app.register_blueprint(bp)
    app.before_request(load_user)

    with app.app_context():
        @event.listens_for(db.engine, "connect")
        def configure_sqlite(connection, _):
            # В SQLite контроль внешних ключей включается для каждого подключения.
            connection.execute("PRAGMA foreign_keys=ON")
        db.create_all()

    @app.after_request
    def security_headers(response):
        """Ограничиваем загрузку ресурсов и запрещаем кеширование личных данных."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        """Открываем кабинет или страницу входа в зависимости от сессии."""
        return redirect(url_for("profile" if g.user else "auth.login"))

    @app.get("/profile")
    @login_required
    def profile():
        """Выбираем только объекты текущего пользователя."""
        reminders = db.session.scalars(db.select(Reminder).where(Reminder.user_id == g.user.id).order_by(Reminder.due_at.desc())).all()
        return render_template("profile.html", reminders=reminders)

    @app.post("/reminders")
    @login_required
    def add_reminder():
        """Преобразуем дату с явным часовым поясом в UTC и сохраняем объект."""
        message = request.form.get("message", "").strip()
        try:
            due = datetime.fromisoformat(request.form.get("due_at", "").replace("Z", "+00:00"))
            if due.tzinfo is None:
                raise ValueError("Укажите часовой пояс")
            due = due.astimezone(timezone.utc).replace(tzinfo=None)
            if not 1 <= len(message) <= 500:
                raise ValueError("Длина сообщения: 1–500 символов")
        except (ValueError, OverflowError):
            # Смещение часового пояса может вывести граничную дату за диапазон UTC.
            flash("Введите сообщение и выберите корректные дату и время в календаре.", "error")
            return redirect(url_for("profile"))
        # Владельца определяет сервер; значение из формы никогда не используется.
        db.session.add(Reminder(user_id=g.user.id, message=message, due_at=due))
        db.session.commit()
        flash("Напоминание сохранено. Прошедшее время будет обработано при ближайшей проверке планировщика.", "success")
        return redirect(url_for("profile"))

    @app.get("/notifications")
    @login_required
    def notifications():
        """Передаём браузеру отметки доставки только текущего пользователя."""
        delivered_ids = db.session.scalars(db.select(Reminder.id).where(
            Reminder.user_id == g.user.id, Reminder.delivered_at.is_not(None)
        )).all()
        return jsonify(delivered_ids=delivered_ids)

    @app.post("/reminders/<int:reminder_id>/delete")
    @login_required
    def delete_reminder(reminder_id):
        """Удаляем объект только при совпадении его владельца с пользователем."""
        reminder = db.session.scalar(db.select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == g.user.id))
        if reminder is None:
            abort(404)
        db.session.delete(reminder)
        db.session.commit()
        return redirect(url_for("profile"))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
