"""Модели пользователей, серверных сессий и персональных напоминаний."""

from datetime import datetime, timezone
from database import db


def utcnow():
    # SQLite хранит даты без часового пояса; в базе все значения относятся к UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    """Учётная запись: вместо открытого пароля сохраняется только его хеш."""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class LoginSession(db.Model):
    """Серверная сессия с хешем токена и ограниченным сроком действия."""
    __tablename__ = "login_sessions"
    token_hash = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)


class Reminder(db.Model):
    """Напоминание владельца; отметка доставки превращает его в уведомление."""
    __tablename__ = "reminders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    message = db.Column(db.String(500), nullable=False)
    due_at = db.Column(db.DateTime, index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    delivered_at = db.Column(db.DateTime)
