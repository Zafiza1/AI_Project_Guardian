from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.core.config import settings


def utcnow() -> datetime:
    # Stored as naive UTC; the API layer attaches the UTC timezone when serializing.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_engine(url: str):
    if url.startswith("sqlite:///"):
        db_path = url.removeprefix("sqlite:///")
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String(255), nullable=False)
    repository_path = Column(String(1024), nullable=False, unique=True)
    # ID of an entry in the check-command allowlist (never a raw shell string).
    check_command = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    health_checks = relationship(
        "HealthCheck", back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    # success | failed | timeout | error
    status = Column(String(32), nullable=False)
    branch = Column(String(255), nullable=True)
    is_clean = Column(Boolean, nullable=True)
    changed_files = Column(Integer, nullable=True)
    check_command = Column(String(64), nullable=True)
    exit_code = Column(Integer, nullable=True)
    duration_ms = Column(Float, nullable=False)
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utcnow, index=True)

    project = relationship("Project", back_populates="health_checks")
    diagnoses = relationship("Diagnosis", back_populates="health_check", cascade="all, delete-orphan", passive_deletes=True)


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(Integer, primary_key=True, index=True)
    health_check_id = Column(Integer, ForeignKey("health_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    # pending | completed | failed
    status = Column(String(32), nullable=False)
    provider = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    # Structured findings stored as JSON
    findings = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)

    health_check = relationship("HealthCheck", back_populates="diagnoses")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
