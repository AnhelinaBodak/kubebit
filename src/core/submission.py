from hmac import compare_digest

from db import db
from models import Challenge, Solve, Submission, Team, User
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from core.competition import calculate_points_awarded


def _clean_flag(flag: str) -> str:
    return (flag or "").strip()


def _is_first_blood(challenge_id: int) -> bool:
    return not Solve.query.filter_by(challenge_id=challenge_id).first()


def submit_flag(user_id: int, challenge_id: int, submitted_flag: str):
    submitted_flag = _clean_flag(submitted_flag)
    if not submitted_flag:
        raise ValueError("Submitted flag cannot be empty")

    team_id = None

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

            if user.team_id is None:
                raise ValueError("User must belong to a team before submitting flags")

            team_id = user.team_id

            team = (
                db.session.query(Team)
                .filter(Team.id == team_id)
                .with_for_update()
                .first()
            )
            if not team:
                raise ValueError("Team not found")

            challenge = (
                db.session.query(Challenge)
                .filter(Challenge.id == challenge_id)
                .with_for_update()
                .first()
            )
            if not challenge:
                raise ValueError("Challenge not found")

            existing_solve = Solve.query.filter_by(
                team_id=team.id,
                challenge_id=challenge.id
            ).first()
            if existing_solve:
                return {
                    "status": "already_solved",
                    "correct": True,
                    "team_id": team.id,
                    "user_id": user.id,
                    "challenge_id": challenge.id,
                    "points_awarded": 0
                }

            attempts_used = Submission.query.filter_by(
                team_id=team.id,
                challenge_id=challenge.id
            ).count()

            if challenge.max_attempts is not None and attempts_used >= challenge.max_attempts:
                raise ValueError("Maximum attempts reached")

            is_correct = compare_digest(submitted_flag, _clean_flag(challenge.flag))

            submission = Submission(
                team_id=team.id,
                user_id=user.id,
                challenge_id=challenge.id,
                submitted_flag=submitted_flag,
                is_correct=is_correct
            )
            db.session.add(submission)
            db.session.flush()

            if not is_correct:
                attempts_after_submission = attempts_used + 1
                return {
                    "status": "incorrect",
                    "correct": False,
                    "submission_id": submission.id,
                    "team_id": team.id,
                    "user_id": user.id,
                    "challenge_id": challenge.id,
                    "attempts_used": attempts_after_submission,
                    "attempts_left": challenge.max_attempts - attempts_after_submission if challenge.max_attempts is not None else None
                }

            solves_count = Solve.query.filter_by(challenge_id=challenge.id).count()
            points_awarded = calculate_points_awarded(
                challenge.base_points,
                challenge.min_points,
                solves_count
            )
            first_blood = _is_first_blood(challenge.id)

            solve = Solve(
                team_id=user.team_id,
                user_id=user.id,
                challenge_id=challenge.id,
                is_first_blood=first_blood,
                points_awarded=points_awarded
            )
            db.session.add(solve)

            team.points += points_awarded
            user.points += points_awarded

            return {
                "status": "correct",
                "correct": True,
                "submission_id": submission.id,
                "team_id": team.id,
                "user_id": user.id,
                "challenge_id": challenge.id,
                "points_awarded": points_awarded,
                "is_first_blood": first_blood
            }

    except IntegrityError:
        db.session.rollback()
        return {
            "status": "already_solved",
            "correct": True,
            "team_id": team_id,
            "user_id": user_id,
            "challenge_id": challenge_id,
            "points_awarded": 0
        }
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_submissions_for_team(team_id: int, challenge_id: int | None = None):
    query = Submission.query.filter_by(team_id=team_id)

    if challenge_id is not None:
        query = query.filter_by(challenge_id=challenge_id)

    return query.order_by(Submission.submitted_at.desc()).all()


def has_team_solved(team_id: int, challenge_id: int) -> bool:
    return Solve.query.filter_by(
        team_id=team_id,
        challenge_id=challenge_id
    ).first() is not None


def list_user_solves(user_id: int):
    solves = (
        Solve.query
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .filter(Solve.user_id == user_id)
        .order_by(Solve.solved_at.desc())
        .all()
    )

    return [
        {
            "id": solve.id,
            "challenge_id": solve.challenge_id,
            "challenge_name": solve.challenge.name,
            "category_name": solve.challenge.category.name if solve.challenge.category else None,
            "points_awarded": solve.points_awarded,
            "is_first_blood": solve.is_first_blood,
            "solved_at": solve.solved_at.isoformat() if solve.solved_at else None
        }
        for solve in solves
    ]


def list_team_solves(team_id: int):
    solves = (
        Solve.query
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .filter(Solve.team_id == team_id)
        .order_by(Solve.solved_at.desc())
        .all()
    )

    return [
        {
            "id": solve.id,
            "team_id": solve.team_id,
            "user_id": solve.user_id,
            "solver_username": solve.user.username if solve.user else None,
            "challenge_id": solve.challenge_id,
            "challenge_name": solve.challenge.name,
            "category_name": solve.challenge.category.name if solve.challenge.category else None,
            "points_awarded": solve.points_awarded,
            "is_first_blood": solve.is_first_blood,
            "solved_at": solve.solved_at.isoformat() if solve.solved_at else None
        }
        for solve in solves
    ]
