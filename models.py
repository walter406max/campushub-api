from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String

from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class StudentUser(Base):
    __tablename__ = "student_users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    university = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    income = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class BudgetItem(Base):
    __tablename__ = "budget_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("student_users.id"), index=True, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    week = Column(String, nullable=False)
    timestamp = Column(DateTime, default=utcnow)
    # UUID made by the phone for each expense, so a retried sync never creates duplicates
    client_id = Column(String(64), nullable=True, index=True)

    # Sync optimization flags
    last_updated = Column(DateTime, default=utcnow, onupdate=utcnow)
    is_synced = Column(Boolean, default=False)


class MarketplaceItem(Base):
    __tablename__ = "marketplace_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    contact_details = Column(String, nullable=False)
    seller_id = Column(Integer, ForeignKey("student_users.id"), index=True, nullable=False)
    timestamp = Column(DateTime, default=utcnow)

    # Sync optimization flags
    last_updated = Column(DateTime, default=utcnow, onupdate=utcnow)
    is_synced = Column(Boolean, default=False)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    type = Column(String, nullable=False)
    deadline = Column(Date, nullable=False)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("student_users.id"), index=True, nullable=False)
    category = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)