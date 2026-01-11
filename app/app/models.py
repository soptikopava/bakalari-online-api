from datetime import datetime
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_type: Mapped[str] = mapped_column(String(10))  # current|next
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str] = mapped_column(String(500), default="")

from sqlalchemy import Column, Integer, String, UniqueConstraint, DateTime
import datetime as dt
from app.db import Base

class RoomTeacherMap(Base):
    __tablename__ = "room_teacher_map"

    id = Column(Integer, primary_key=True, index=True)

    room_id = Column(String, index=True, nullable=False)     # "06"
    week = Column(String, index=True, nullable=False)        # "actual" / "next"
    day_index = Column(Integer, index=True, nullable=False)  # 1..5
    lesson = Column(Integer, index=True, nullable=False)     # 0..14

    teacher_id = Column(String, index=True, nullable=False)  # "UL00R"
    teacher_name = Column(String, nullable=True)

    score = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("room_id", "week", "day_index", "lesson", name="uq_room_week_day_lesson"),
    )