from db import db
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, Enum, DateTime, func
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

class ChallengeType(enum.Enum):
    CONTAINER = "container"
    STATIC = "static"
    CONTAINER_STATIC = "container_static"

class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"
    AUDITOR = "auditor"

class Competition(db.Model):
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)

    min_team_size = Column(Integer, default=1)
    max_team_size = Column(Integer, default=5)

    teams = relationship("Team", back_populates="competition")

class User(db.Model):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    username = Column(String(120), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    role = Column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.USER
    )

    password_hash = Column(String(255), nullable=False)
    points = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), unique=False)
    team = relationship("Team", back_populates="users", foreign_keys=[team_id])


class Team(db.Model):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    points = Column(Integer, default=0, nullable=False)
    captain_id = Column(Integer, ForeignKey("users.id"))
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=True)

    captain = relationship("User", foreign_keys=[captain_id])
    users = relationship("User", back_populates="team", foreign_keys="User.team_id", lazy="dynamic")

    solves = relationship("Solve", back_populates="team")
    competition = relationship("Competition", back_populates="teams")


class Challenge(db.Model):
    __tablename__ = "challenges"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text)
    base_points = Column(Integer, nullable=False)
    min_points = Column(Integer, nullable=False, default=0)
    type = Column(Enum(ChallengeType, name="challenge_type_enum"), nullable=False)
    max_attempts = Column(Integer, nullable=True)
    flag = Column(String(255), nullable=False)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    category = relationship("Category", back_populates="challenges")

    container_challenge = relationship("ContainerChallenge", back_populates="challenge", 
                                       uselist=False, cascade="all, delete")

    file_challenge = relationship("FileChallenge", back_populates="challenge", 
                                       uselist=False, cascade="all, delete")
    
    container_file_challenge = relationship("ContainerFileChallenge", back_populates="challenge", 
                                       uselist=False, cascade="all, delete")


class ContainerChallenge(db.Model):
    __tablename__ = "container_challenges"
    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, unique=True)

    docker_image = Column(String(255), nullable=False)
    container_port = Column(Integer, nullable=False)
    cpu_limit = Column(String(50))
    memory_limit = Column(String(50))

    challenge = relationship("Challenge", back_populates="container_challenge")


class ContainerFileChallenge(db.Model):
    __tablename__ = "container_file_challenges"
    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, unique=True)

    docker_image = Column(String(255), nullable=False)
    container_port = Column(Integer, nullable=False)
    cpu_limit = Column(String(50))
    memory_limit = Column(String(50))
    file_path = Column(String(255))
    external_url = Column(String(255))

    challenge = relationship("Challenge", back_populates="container_file_challenge")


class FileChallenge(db.Model):
    __tablename__ = "file_challenges"
    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, unique=True)
    file_path = Column(String(255))
    external_url = Column(String(255))

    challenge = relationship("Challenge", back_populates="file_challenge")


class Category(db.Model):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)

    challenges = relationship("Challenge", back_populates="category")


class Solve(db.Model):
    __tablename__ = "solves"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    is_first_blood = Column(Boolean, default=False, nullable=False)
    points_awarded = Column(Integer, nullable=False)
    solved_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        db.UniqueConstraint("team_id", "challenge_id", name="unique_team_challenge"),
    )

    team = relationship("Team", back_populates="solves")
    user = relationship("User")
    challenge = relationship("Challenge")


class Submission (db.Model):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    submitted_flag = Column(String(255), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
