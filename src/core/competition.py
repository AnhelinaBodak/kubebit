from datetime import datetime, timezone
from threading import RLock

from db import db
from models import Competition, ScoringMode
from scoring import fixed_decay_score
from sqlalchemy.exc import SQLAlchemyError


DEFAULT_COMPETITION_NAME = "Default competition"

_cache_lock = RLock()
_scoring_cache = {
    "loaded": False,
    "competition_id": None,
    "scoring_mode": ScoringMode.NO_DECAY.value,
    "fixed_decay_rate": 0,
    "started_at": None,
}


def _competition_query(for_update: bool = False):
    query = db.session.query(Competition).order_by(Competition.id)
    if for_update:
        query = query.with_for_update()
    return query


def _get_or_create_competition(for_update: bool = False):
    competition = _competition_query(for_update=for_update).first()
    if competition:
        return competition

    competition = Competition(
        name=DEFAULT_COMPETITION_NAME,
        scoring_mode=ScoringMode.NO_DECAY,
        fixed_decay_rate=0,
    )
    db.session.add(competition)
    db.session.flush()
    return competition


def _payload(competition: Competition):
    return {
        "id": competition.id,
        "name": competition.name,
        "scoring_mode": competition.scoring_mode.value,
        "fixed_decay_rate": competition.fixed_decay_rate,
        "started": competition.started_at is not None,
        "started_at": competition.started_at.isoformat() if competition.started_at else None,
    }


def _store_scoring_cache(competition: Competition):
    with _cache_lock:
        _scoring_cache["loaded"] = True
        _scoring_cache["competition_id"] = competition.id
        _scoring_cache["scoring_mode"] = competition.scoring_mode.value
        _scoring_cache["fixed_decay_rate"] = competition.fixed_decay_rate
        _scoring_cache["started_at"] = competition.started_at


def _clear_scoring_cache():
    with _cache_lock:
        _scoring_cache["loaded"] = False
        _scoring_cache["competition_id"] = None
        _scoring_cache["scoring_mode"] = ScoringMode.NO_DECAY.value
        _scoring_cache["fixed_decay_rate"] = 0
        _scoring_cache["started_at"] = None


def get_competition_settings():
    competition = _competition_query().first()
    if competition:
        return _payload(competition)

    competition = Competition(
        name=DEFAULT_COMPETITION_NAME,
        scoring_mode=ScoringMode.NO_DECAY,
        fixed_decay_rate=0,
    )

    try:
        db.session.add(competition)
        db.session.commit()
        return _payload(competition)
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _parse_scoring_mode(value: str | None):
    try:
        return ScoringMode((value or ScoringMode.NO_DECAY.value).lower())
    except ValueError:
        raise ValueError("Invalid scoring mode")


def _optional_int(value, field_name: str):
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer")


def update_scoring_config(data: dict):
    scoring_mode = _parse_scoring_mode(data.get("scoring_mode"))
    fixed_decay_rate = _optional_int(data.get("fixed_decay_rate", 0), "Fixed decay rate")

    if fixed_decay_rate is None:
        fixed_decay_rate = 0
    if fixed_decay_rate < 0:
        raise ValueError("Fixed decay rate cannot be negative")

    with db.session.begin():
        competition = _get_or_create_competition(for_update=True)
        if competition.started_at is not None:
            raise ValueError("Scoring settings cannot be changed after competition starts")

        competition.scoring_mode = scoring_mode
        competition.fixed_decay_rate = fixed_decay_rate
        result = _payload(competition)

    _clear_scoring_cache()

    return result


def start_competition():
    with db.session.begin():
        competition = _get_or_create_competition(for_update=True)
        if competition.started_at is None:
            competition.started_at = datetime.now(timezone.utc)

        result = _payload(competition)
        _store_scoring_cache(competition)

    return result


def load_scoring_config():
    with _cache_lock:
        if _scoring_cache["loaded"]:
            return {
                "fixed_decay_rate": _scoring_cache["fixed_decay_rate"],
                "scoring_mode": _scoring_cache["scoring_mode"],
                "started_at": _scoring_cache["started_at"],
            }

    competition = _get_or_create_competition()
    if competition.started_at is not None:
        _store_scoring_cache(competition)

    return {
        "fixed_decay_rate": competition.fixed_decay_rate,
        "scoring_mode": competition.scoring_mode.value,
        "started_at": competition.started_at,
    }


def calculate_points_awarded(base_points: int, min_points: int, solves_count: int):
    config = load_scoring_config()
    scoring_mode = config["scoring_mode"]

    if scoring_mode == ScoringMode.NO_DECAY.value:
        return base_points

    if scoring_mode == ScoringMode.FIXED_DECAY.value:
        return fixed_decay_score(
            base_points,
            config["fixed_decay_rate"],
            solves_count,
            min_points
        )

    return base_points
