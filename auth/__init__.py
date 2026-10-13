"""Регистрация, проверка паролей и управление серверными сессиями."""

import hashlib
import secrets
from datetime import timedelta
from functools import wraps

from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from database import db
from models import LoginSession, User, utcnow

bp = Blueprint("auth", __name__)
# Проверка хеша выполняется и для отсутствующего аккаунта, с той же стоимостью.
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32))


def digest(token):
    """Хешируем случайный токен, чтобы не хранить его открыто в базе."""
    return hashlib.sha256(token.encode()).hexdigest()


def load_user():
    """Определяем пользователя только по существующей и непросроченной сессии."""
    g.user = None
    token = session.get("token")
    if token:
        record = db.session.get(LoginSession, digest(token))
        if record and record.expires_at > utcnow():
            g.user = db.session.get(User, record.user_id)


def login_required(view):
    """Закрываем доступ к обработчику для неавторизованных посетителей."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Проверяем поля и создаём пользователя с уникальными логином и почтой."""
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        try:
            email = validate_email(request.form.get("email", "").strip(), check_deliverability=False).normalized.lower()
            if not (3 <= len(username) <= 40 and username.isascii() and all(c.isalnum() or c == "_" for c in username)):
                raise ValueError("Логин: 3–40 латинских букв, цифр или символов _.")
            if not 12 <= len(password) <= 128:
                raise ValueError("Пароль должен содержать от 12 до 128 символов.")
            db.session.add(User(username=username, email=email, password_hash=generate_password_hash(password, method="scrypt")))
            db.session.commit()
        except (EmailNotValidError, ValueError) as error:
            flash(str(error), "error")
            return render_template("register.html"), 400
        except IntegrityError:
            db.session.rollback()
            flash("Не удалось зарегистрироваться. Используйте другой логин или email.", "error")
            return render_template("register.html"), 409
        flash("Аккаунт создан. Войдите с вашим паролем.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Проверяем пароль и создаём новую сессию на восемь часов."""
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if len(password) > 128:
            password = ""
        user = db.session.scalar(db.select(User).where(User.username == username))
        valid = check_password_hash(user.password_hash if user else DUMMY_HASH, password)
        if not user or not valid:
            flash("Неверный логин или пароль.", "error")
            return render_template("login.html"), 401
        old_token = session.get("token")
        if old_token:
            db.session.execute(db.delete(LoginSession).where(LoginSession.token_hash == digest(old_token)))
        # Удаляем прежнее содержимое cookie перед выдачей нового токена.
        session.clear()
        token = secrets.token_urlsafe(32)
        session["token"] = token
        db.session.add(LoginSession(token_hash=digest(token), user_id=user.id, expires_at=utcnow() + timedelta(hours=8)))
        db.session.commit()
        return redirect(url_for("profile"))
    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    """Отзываем токен в базе: копия старого cookie больше не даёт доступа."""
    db.session.execute(db.delete(LoginSession).where(LoginSession.token_hash == digest(session["token"])))
    db.session.commit()
    session.clear()
    return redirect(url_for("auth.login"))
