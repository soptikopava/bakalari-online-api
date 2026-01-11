from sqlalchemy import String, Integer, Boolean, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.core.db import Base

class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_type: Mapped[str] = mapped_column(String(10))  # current|next
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|ok|fail
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

class Teacher(Base):
    __tablename__ = "teachers"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # Bakalari ID or slug
    name: Mapped[str] = mapped_column(String(200))
    short: Mapped[str | None] = mapped_column(String(50), nullable=True)

class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"))
    week_type: Mapped[str] = mapped_column(String(10))  # current|next

    entity_type: Mapped[str] = mapped_column(String(10))  # teacher|class|room
    entity_id: Mapped[str] = mapped_column(String(50))

    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD (string to keep it easy)
    lesson_number: Mapped[int] = mapped_column(Integer)

    is_teaching: Mapped[bool] = mapped_column(Boolean, default=False)
    subject: Mapped[str | None] = mapped_column(String(50), nullable=True)
    teacher_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    class_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    room_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "week_type", "entity_type", "entity_id", "date", "lesson_number",
            name="uq_lesson_slot"
        ),
    )
