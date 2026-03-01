from models import User, Team
from db import db
from sqlalchemy.exc import SQLAlchemyError


def create_user(name: str, email: str, password: str):
    if User.query.filter_by(name=name).first():
        raise ValueError("User with this name already exists")

    if User.query.filter_by(email=email).first():
        raise ValueError("User with this email already exists")

    try:
        user = User(name=name, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        return user
    except SQLAlchemyError:
        db.session.rollback()
        raise


def assign_user_to_team(user_id: int, team_id: int):
    user = User.query.get(user_id)
    if not user:
        raise ValueError("User not found")

    team = Team.query.get(team_id)
    if not team:
        raise ValueError("Team not found")

    if user.team_id:
        raise ValueError("User already in a team")

    try:
        user.team_id = team.id
        db.session.commit()
        return user
    except SQLAlchemyError:
        db.session.rollback()
        raise