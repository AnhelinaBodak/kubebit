from models import Category, Challenge, ContainerChallenge, ContainerFileChallenge, FileChallenge, ChallengeType
from db import db
from sqlalchemy.exc import SQLAlchemyError

DEFAULT_CPU_LIMIT = "500m"
DEFAULT_MEMORY_LIMIT = "256Mi"

def create_category(name: str):
    if Category.query.filter_by(name=name).first():
        raise ValueError("Category already exists")

    category = Category(name=name)

    try:
        db.session.add(category)
        db.session.commit()
        return category
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def delete_category(name: str):
    category = Category.query.filter_by(name=name).first()
    if not category:
        raise ValueError("Category not found")

    try:
        db.session.delete(category)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def list_categories():
    return Category.query.all()

def create_container_challenge(
    name: str,
    base_points: int,
    flag: str,
    category_id: int,
    docker_image: str,
    container_port: int,
    min_points: int = 0,
    description: str | None = None,
    max_attempts: int | None = None,
    cpu_limit: str = DEFAULT_CPU_LIMIT,
    memory_limit: str = DEFAULT_MEMORY_LIMIT,
):
    cpu_limit = cpu_limit or DEFAULT_CPU_LIMIT
    memory_limit = memory_limit or DEFAULT_MEMORY_LIMIT

    try:
        with db.session.begin():
            if name and Challenge.query.filter_by(name=name).first():
                raise ValueError("Challenge already exists")

            category = Category.query.get(category_id)
            if not category:
                raise ValueError("Category not found")

            challenge = Challenge(
                name=name,
                description=description,
                base_points=base_points,
                min_points=min_points,
                type=ChallengeType.CONTAINER,
                flag=flag,
                category_id=category_id,
                max_attempts=max_attempts
            )

            db.session.add(challenge)
            db.session.flush()

            config = ContainerChallenge(
                challenge_id=challenge.id,
                docker_image=docker_image,
                container_port=container_port,
                cpu_limit=cpu_limit,
                memory_limit=memory_limit
            )

            db.session.add(config)

        return challenge

    except SQLAlchemyError as e:
        db.session.rollback()
        print("DB ERROR:", e)
        raise

def create_static_challenge(
    name: str,
    base_points: int,
    flag: str,
    category_id: int,
    min_points: int = 0,
    description: str | None = None,
    max_attempts: int | None = None,
    file_path: str | None = None,
    external_url: str | None = None,
):
    try:
        with db.session.begin():
            if name and Challenge.query.filter_by(name=name).first():
                raise ValueError("Challenge already exists")

            category = Category.query.get(category_id)
            if not category:
                raise ValueError("Category not found")
            
            if not file_path and not external_url:
                raise ValueError("Either file_path or external_url must be provided")

            challenge = Challenge(
                name=name,
                description=description,
                base_points=base_points,
                min_points=min_points,
                type=ChallengeType.STATIC,
                flag=flag,
                category_id=category_id,
                max_attempts=max_attempts
            )

            db.session.add(challenge)
            db.session.flush()

            config = FileChallenge(
                challenge_id=challenge.id,
                external_url=external_url,
            )

            db.session.add(config)

        return challenge

    except SQLAlchemyError:
        db.session.rollback()
        raise

def create_container_static_challenge(
    name: str,
    base_points: int,
    flag: str,
    category_id: int,
    docker_image: str,
    container_port: int,
    min_points: int = 0,
    description: str | None = None,
    max_attempts: int | None = None,
    file_path: str | None = None,
    external_url: str | None = None,
    cpu_limit: str = DEFAULT_CPU_LIMIT,
    memory_limit: str = DEFAULT_MEMORY_LIMIT,
):
    cpu_limit = cpu_limit or DEFAULT_CPU_LIMIT
    memory_limit = memory_limit or DEFAULT_MEMORY_LIMIT

    try:
        with db.session.begin():
            if name and Challenge.query.filter_by(name=name).first():
                raise ValueError("Challenge already exists")

            category = Category.query.get(category_id)
            if not category:
                raise ValueError("Category not found")
            
            if not file_path and not external_url:
                raise ValueError("Either file_path or external_url must be provided")

            challenge = Challenge(
                name=name,
                description=description,
                base_points=base_points,
                min_points=min_points,
                type=ChallengeType.CONTAINER_STATIC,
                flag=flag,
                category_id=category_id,
                max_attempts=max_attempts
            )

            db.session.add(challenge)
            db.session.flush()
            config = ContainerFileChallenge(
                challenge_id=challenge.id,
                docker_image=docker_image,
                container_port=container_port,
                cpu_limit=cpu_limit,
                memory_limit=memory_limit,
                file_path=file_path,
                external_url=external_url
            )

            db.session.add(config)

        return challenge

    except SQLAlchemyError:
        raise

def list_challenges():
    return Challenge.query.all()
