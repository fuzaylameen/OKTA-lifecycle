from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime

from app.db.database import Base


class AuditLog(Base):

    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    action = Column(
        String(100),
        nullable=False
    )

    user_id = Column(
        String(100),
        nullable=True
    )

    user_email = Column(
        String(255),
        nullable=True
    )

    old_value = Column(
        Text,
        nullable=True
    )

    new_value = Column(
        Text,
        nullable=True
    )

    status = Column(
        String(50),
        nullable=False
    )

    message = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )