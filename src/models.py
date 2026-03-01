from db import db
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, Enum, DateTime, func
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

class ChallengeType(enum.Enum):
    CONTAINER = "container"
    STATIC = "static"


class User(db.Model):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    points = Column(Integer, default=0, nullable=False)
    
    team_id = Column(Integer, ForeignKey("teams.id"), unique=False)
    team = relationship("Team", back_populates="users", foreign_keys=[team_id])


class Team(db.Model):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    points = Column(Integer, default=0, nullable=False)
    captain_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    captain = relationship("User", foreign_keys=[captain_id])
    users = relationship("User", back_populates="team", foreign_keys="User.team_id", lazy="dynamic", cascade="all, delete")


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


class ContainerChallenge(db.Model):
    __tablename__ = "container_challenges"
    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, unique=True)

    docker_image = Column(String(255), nullable=False)
    container_port = Column(Integer, nullable=False)
    cpu_limit = Column(String(50))
    memory_limit = Column(String(50))

    challenge = relationship("Challenge", back_populates="container_challenge")


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