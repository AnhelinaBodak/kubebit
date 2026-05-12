from models import User, Team, UserRole
from db import db
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from werkzeug.security import generate_password_hash, check_password_hash

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"
DEFAULT_ADMIN_EMAIL = "admin@kubebit.local"

def create_user(name: str, username: str, email: str, password: str, role: str = "user"):
    with db.session.begin():
        if User.query.filter_by(name=name).first():
            raise ValueError("Name already exists")

        if User.query.filter_by(username=username).first():
            raise ValueError("Username already exists")

        if User.query.filter_by(email=email).first():
            raise ValueError("Email already exists")

        try:
            user_role = UserRole((role or "user").lower())
        except ValueError:
            raise ValueError("Invalid user role")

        hashed_password = generate_password_hash(password)

        user = User(
            name=name,
            username=username,
            email=email,
            role=user_role,
            password_hash=hashed_password
        )

        db.session.add(user)
        db.session.flush()

        return user


def ensure_initial_admin():
    admin = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first()
    if admin:
        return admin

    admin = User(
        name="Administrator",
        username=DEFAULT_ADMIN_USERNAME,
        email=DEFAULT_ADMIN_EMAIL,
        role=UserRole.ADMIN,
        password_hash=generate_password_hash(DEFAULT_ADMIN_PASSWORD)
    )

    try:
        db.session.add(admin)
        db.session.commit()
        return admin
    except SQLAlchemyError:
        db.session.rollback()
        raise


def initialize_admin_password(password: str):
    password = (password or "").strip()
    if not password:
        raise ValueError("Password cannot be empty")

    if password == DEFAULT_ADMIN_PASSWORD:
        raise ValueError("Choose a password different from the default")

    admin = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first()
    if not admin:
        admin = ensure_initial_admin()

    if not check_password_hash(admin.password_hash, DEFAULT_ADMIN_PASSWORD):
        raise ValueError("Initial admin password has already been changed")

    try:
        admin.password_hash = generate_password_hash(password)
        db.session.commit()
        return {
            "username": admin.username,
            "status": "password_initialized"
        }
    except SQLAlchemyError:
        db.session.rollback()
        raise


def admin_password_initialization_required():
    admin = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first()
    if not admin:
        return True

    return check_password_hash(admin.password_hash, DEFAULT_ADMIN_PASSWORD)


def authenticate_user(identity: str, password: str):
    identity = (identity or "").strip()
    password = password or ""

    if not identity or not password:
        raise ValueError("Username/email and password are required")

    user = User.query.filter(
        or_(
            User.username == identity,
            User.email == identity
        )
    ).first()

    if not user or not check_password_hash(user.password_hash, password):
        raise ValueError("Invalid username/email or password")

    return user


def assign_user_to_team(user_id: int, team_id: int):
    try:
        with db.session.begin():
            user = (
                db.session.query(User)
                .filter(User.id == user_id)
                .with_for_update()
                .first()
            )
            if not user:
                raise ValueError("User not found")

            team = (
                db.session.query(Team)
                .filter(Team.id == team_id)
                .with_for_update()
                .first()
            )
            if not team:
                raise ValueError("Team not found")

            if user.team_id:
                raise ValueError("User already in a team")

            user.team_id = team.id

            return user
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_users_with_teams():
    users = User.query.order_by(User.id).all()

    return [
        {
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "points": user.points,
            "team_id": user.team_id,
            "team_name": user.team.name if user.team else None
        }
        for user in users
    ]
