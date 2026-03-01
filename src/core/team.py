from models import Team, User
from db import db
from sqlalchemy.exc import SQLAlchemyError


def create_team(name: str, captain_id: int):
    if Team.query.filter_by(name=name).first():
        raise ValueError("Team with this name already exists")

    captain = User.query.get(captain_id)
    if not captain:
        raise ValueError("Captain not found")

    try:
        team = Team(name=name, captain_id=captain_id)
        db.session.add(team)
        db.session.flush()
        captain.team_id = team.id
        db.session.commit()
        return team
    except SQLAlchemyError:
        db.session.rollback()
        raise


def delete_team(name: str):
    team = Team.query.filter_by(name=name).first()
    if not team:
        raise ValueError("Team not found")

    try:
        db.session.delete(team)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise