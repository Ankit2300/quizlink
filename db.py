"""Database layer. SQLite locally; set DATABASE_URL for Postgres in production."""
import os
import secrets
from datetime import datetime, timezone

from sqlalchemy import (JSON, Column, DateTime, ForeignKey, Integer, String,
                        Text, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./quizlink.db")
if DATABASE_URL.startswith("postgres://"):  # Render/Neon style -> SQLAlchemy style
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


def now():
    return datetime.now(timezone.utc)


def new_code(n=6):
    return secrets.token_urlsafe(8)[:n].replace("-", "x").replace("_", "y").lower()


class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    login = Column(String(120), unique=True, nullable=False)  # dummy login id, not a real email
    password = Column(String(120), nullable=False)
    mcp_key = Column(String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(16))
    quizzes = relationship("Quiz", back_populates="teacher")


class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    time_limit_min = Column(Integer, default=15)
    share_code = Column(String(16), unique=True, nullable=False, default=new_code)
    status = Column(String(16), default="published")  # draft | published | closed
    created_at = Column(DateTime(timezone=True), default=now)
    teacher = relationship("Teacher", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", order_by="Question.position",
                             cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="quiz", order_by="Attempt.submitted_at.desc()",
                            cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    position = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # list[str]
    correct_index = Column(Integer, nullable=False)
    explanation = Column(Text, default="")
    topic = Column(String(120), default="")
    quiz = relationship("Quiz", back_populates="questions")


class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    student_name = Column(String(120), nullable=False)
    answers = Column(JSON, nullable=False)  # {question_id: chosen_index}
    score = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=now)
    quiz = relationship("Quiz", back_populates="attempts")


DEMO_LOGIN = "demo@quizlink.test"
DEMO_PASSWORD = "demo1234"


def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if not s.query(Teacher).filter_by(login=DEMO_LOGIN).first():
            s.add(Teacher(name="Demo Teacher", login=DEMO_LOGIN, password=DEMO_PASSWORD,
                          mcp_key=os.environ.get("DEMO_MCP_KEY", "demo")))
            s.commit()
