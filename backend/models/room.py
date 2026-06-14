"""Physical rooms / halls used when scheduling section meetings.

A small catalog so the offering builder can offer a real room dropdown instead
of a free-text box. `room_type` ('lab' | 'lecture') just groups them in the UI;
the chosen room name is what gets stored on SectionMeeting.location.
"""
from typing import Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Room(Base):
    __tablename__ = "rooms"

    room_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    room_type: Mapped[str] = mapped_column(String(20), default="lecture", nullable=False)  # lab | lecture
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
