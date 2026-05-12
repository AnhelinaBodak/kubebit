from models import Team, User, Competition
from db import db

def create_team(name: str, captain_user_id: int | None = None):
    with db.session.begin():
        if Team.query.filter_by(name=name).first():
            raise ValueError("Team name already exists")

        team = Team(
            name=name
        )

        db.session.add(team)
        db.session.flush()

        if captain_user_id is not None:
            captain = (
                db.session.query(User)
                .filter(User.id == captain_user_id)
                .with_for_update()
                .first()
            )

            if not captain:
                raise ValueError("Captain not found")

            if captain.team_id is not None:
                raise ValueError("User already in a team")

            captain.team_id = team.id
            team.captain_id = captain.id

        return {
            "team_id": team.id,
            "team_name": team.name,
            "captain_id": team.captain_id
        }

def assign_captain(team_id: int, captain_user_id: int):
    with db.session.begin():
        team = (
            db.session.query(Team)
            .filter(Team.id == team_id)
            .with_for_update()
            .first()
        )
        if not team:
            raise ValueError("Team not found")

        captain = (
            db.session.query(User)
            .filter(User.id == captain_user_id)
            .with_for_update()
            .first()
        )
        if not captain:
            raise ValueError("Captain not found")

        if captain.team_id is not None and captain.team_id != team.id:
            raise ValueError("User already in another team")

        captain.team_id = team.id
        team.captain_id = captain.id

        return {
            "team_id": team.id,
            "captain_id": captain.id
        }

def list_teams():
    teams = Team.query.order_by(Team.id).all()

    return [
        {
            "id": team.id,
            "name": team.name,
            "points": team.points,
            "captain_id": team.captain_id,
            "captain_username": team.captain.username if team.captain else None,
            "competition_id": team.competition_id,
            "member_count": team.users.count()
        }
        for team in teams
    ]

def list_users_in_team(team_id: int):
    team = Team.query.get(team_id)
    if not team:
        raise ValueError("Team not found")

    return {
        "team_id": team.id,
        "team_name": team.name,
        "users": [
            {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "points": user.points,
                "is_captain": team.captain_id == user.id
            }
            for user in team.users.order_by(User.id).all()
        ]
    }

def update_team_name(team_id: int, requester_user_id: int, new_name: str, is_admin: bool = False):
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("Team name cannot be empty")

    with db.session.begin():
        team = (
            db.session.query(Team)
            .filter(Team.id == team_id)
            .with_for_update()
            .first()
        )
        if not team:
            raise ValueError("Team not found")

        if not is_admin and team.captain_id != requester_user_id:
            raise ValueError("Only captain can rename the team")

        existing = Team.query.filter(Team.name == new_name, Team.id != team_id).first()
        if existing:
            raise ValueError("Team name already exists")

        team.name = new_name

        return {"team_id": team.id, "name": team.name}

def join_team(user_id: int, team_id: int):
    with db.session.begin():
        user = (
            db.session.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )

        if not user:
            raise ValueError("User not found")

        if user.team_id is not None:
            raise ValueError("User already in a team")

        team = (
            db.session.query(Team)
            .filter(Team.id == team_id)
            .with_for_update()
            .first()
        )

        if not team:
            raise ValueError("Team not found")

        current_members = team.users.count()

        if current_members >= Competition.max_team_size:
            raise ValueError("Team is full")

        user.team_id = team.id

        return {
            "team_id": team.id,
            "user_id": user.id,
            "current_members": current_members + 1
        }
    
def leave_team(user_id: int):
    with db.session.begin():
        user = (
            db.session.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )

        if not user or not user.team_id:
            raise ValueError("User not in team")

        team = (
            db.session.query(Team)
            .filter(Team.id == user.team_id)
            .with_for_update()
            .first()
        )

        if team.captain_id == user.id and team.users.count() > 1:
            raise ValueError("Captain must transfer leadership before leaving")

        user.team_id = None

        return {
            "user_id": user.id,
            "left_team": team.id
        }

def transfer_captain(team_id: int, new_captain_id: int):
    with db.session.begin():
        team = (
            db.session.query(Team)
            .filter(Team.id == team_id)
            .with_for_update()
            .first()
        )

        if not team:
            raise ValueError("Team not found")

        new_captain = (
            db.session.query(User)
            .filter(User.id == new_captain_id)
            .with_for_update()
            .first()
        )

        if not new_captain or new_captain.team_id != team.id:
            raise ValueError("New captain must belong to the team")

        team.captain_id = new_captain.id

        return {
            "team_id": team.id,
            "new_captain_id": new_captain.id
        }

def check_team_capacity(team_id: int):
    team = Team.query.get(team_id)

    if not team:
        raise ValueError("Team not found")

    current_members = team.users.count()

    if current_members < team.min_capacity:
        return {
            "allowed": False,
            "reason": "Team below minimum capacity",
            "current_members": current_members,
            "min_required": team.min_capacity
        }

    if team.max_capacity and current_members > team.max_capacity:
        return {
            "allowed": False,
            "reason": "Team exceeds maximum capacity",
            "current_members": current_members,
            "max_allowed": team.max_capacity
        }

    return {
        "allowed": True,
        "current_members": current_members
    }
