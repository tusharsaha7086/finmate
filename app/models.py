"""
SQLModel table definitions.

Tables:
  - users         — one row per WhatsApp phone number
  - transactions  — income / expense records linked to a user
  - tasks         — to-do items / reminders linked to a user
  - health_logs   — health metric entries (water, steps, …) linked to a user
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, Relationship, SQLModel


class TransactionType(str, enum.Enum):
    """Allowed transaction directions."""
    INCOME = "income"
    EXPENSE = "expense"


class User(SQLModel, table=True):
    """Represents a WhatsApp user identified by phone number."""
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    phone_number: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    transactions: list["Transaction"] = Relationship(back_populates="user")
    tasks: list["Task"] = Relationship(back_populates="user")
    health_logs: list["HealthLog"] = Relationship(back_populates="user")


class Transaction(SQLModel, table=True):
    """A single income or expense entry belonging to a User."""
    __tablename__ = "transactions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    type: TransactionType
    category: str = Field(default="general")
    description: str = Field(default="")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    user: User | None = Relationship(back_populates="transactions")


class Task(SQLModel, table=True):
    """A to-do / reminder item belonging to a User."""
    __tablename__ = "tasks"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    description: str
    due_date: datetime | None = Field(default=None)
    status: str = Field(default="pending")
    reminder_sent: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: User | None = Relationship(back_populates="tasks")


class HealthLog(SQLModel, table=True):
    """A single health-metric entry (water, steps, etc.) belonging to a User."""
    __tablename__ = "health_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    metric_type: str = Field(index=True)
    value: float
    unit: str = Field(default="ml")
    logged_at: datetime = Field(default_factory=datetime.utcnow)

    user: User | None = Relationship(back_populates="health_logs")
