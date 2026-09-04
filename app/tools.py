"""
Agno Toolkits exposing CRUD operations on the application DB.

FinanceTools    — income / expense tracking
AssistantTools  — task management & health-metric logging

Every public method becomes a tool the LLM can call.  Each tool receives the
user's phone number so it can resolve (or create) the correct User row before
operating on the database.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from agno.tools import Toolkit
from sqlmodel import Session, select

from app.database import engine
from app.models import HealthLog, Task, Transaction, TransactionType, User

logger = logging.getLogger("finmate.tools")


class FinanceTools(Toolkit):
    def __init__(self) -> None:
        tools = [
            self.add_transaction,
            self.get_balance,
            self.get_transactions,
            self.get_spending_by_category,
            self.get_spending_by_date,
        ]
        super().__init__(name="finance_tools", tools=tools)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_or_create_user(self, session: Session, phone: str) -> User:
        """Look up a user by phone; create a new row on first contact."""
        stmt = select(User).where(User.phone_number == phone)
        user = session.exec(stmt).first()
        if not user:
            logger.info("First-time user, creating record for %s", phone)
            user = User(phone_number=phone)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    # ── tools (exposed to the LLM) ──────────────────────────────────────────

    def add_transaction(
        self,
        phone: str,
        amount: float,
        type: str,
        category: str = "general",
        description: str = "",
    ) -> str:
        """
        Record a financial transaction for the user.

        Args:
            phone: The user's WhatsApp phone number (e.g. 'whatsapp:+1234567890').
            amount: The monetary amount of the transaction.
            type: Either 'income' or 'expense'.
            category: Spending category (e.g. 'food', 'rent', 'salary').
            description: Optional note about the transaction.

        Returns:
            A confirmation message with the saved transaction details.
        """
        logger.info(
            "add_transaction called → phone=%s amount=%s type=%s category=%s desc=%r",
            phone, amount, type, category, description,
        )

        # Validate transaction type
        try:
            tx_type = TransactionType(type.lower())
        except ValueError:
            logger.warning("Invalid transaction type received: %r", type)
            return f"Invalid transaction type '{type}'. Use 'income' or 'expense'."

        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                tx = Transaction(
                    user_id=user.id,  # type: ignore[arg-type]
                    amount=Decimal(str(amount)),
                    type=tx_type,
                    category=category.lower(),
                    description=description,
                )
                session.add(tx)
                session.commit()
                session.refresh(tx)

                msg = (
                    f"Saved {tx_type.value}: ₹{tx.amount} "
                    f"[{tx.category}] — {tx.description or 'no description'}"
                )
                logger.info("Transaction saved: id=%s %s", tx.id, msg)
                return msg
        except Exception as e:
            logger.exception("add_transaction failed")
            return f"Error saving transaction: {e}"

    def get_balance(self, phone: str) -> str:
        """
        Calculate the current balance (total income minus total expenses).

        Args:
            phone: The user's WhatsApp phone number.

        Returns:
            A summary showing total income, total expenses, and net balance.
        """
        logger.info("get_balance called → phone=%s", phone)
        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                stmt = select(Transaction).where(Transaction.user_id == user.id)
                transactions = session.exec(stmt).all()

                income = sum(t.amount for t in transactions if t.type == TransactionType.INCOME)
                expenses = sum(t.amount for t in transactions if t.type == TransactionType.EXPENSE)
                balance = income - expenses

                logger.info(
                    "Balance for %s → income=₹%s expenses=₹%s balance=₹%s",
                    phone, income, expenses, balance,
                )
                return (
                    f"💰 Income: ₹{income}\n"
                    f"💸 Expenses: ₹{expenses}\n"
                    f"📊 Balance: ₹{balance}"
                )
        except Exception as e:
            logger.exception("get_balance failed")
            return f"Error fetching balance: {e}"

    def get_transactions(self, phone: str, limit: int = 10) -> str:
        """
        Retrieve the most recent transactions for the user.

        Args:
            phone: The user's WhatsApp phone number.
            limit: Maximum number of transactions to return (default 10).

        Returns:
            A formatted list of recent transactions, or a message if none exist.
        """
        logger.info("get_transactions called → phone=%s limit=%d", phone, limit)
        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                stmt = (
                    select(Transaction)
                    .where(Transaction.user_id == user.id)
                    .order_by(Transaction.timestamp.desc())  # type: ignore[union-attr]
                    .limit(limit)
                )
                transactions = session.exec(stmt).all()

                if not transactions:
                    logger.info("No transactions found for %s", phone)
                    return "No transactions found. Start by telling me about your income or expenses!"

                lines: list[str] = []
                for tx in transactions:
                    sign = "+" if tx.type == TransactionType.INCOME else "-"
                    lines.append(
                        f"{sign}₹{tx.amount} [{tx.category}] "
                        f"{tx.description} — {tx.timestamp:%Y-%m-%d}"
                    )

                logger.info("Returning %d transactions for %s", len(lines), phone)
                return "\n".join(lines)
        except Exception as e:
            logger.exception("get_transactions failed")
            return f"Error fetching transactions: {e}"

    def get_spending_by_category(self, phone: str) -> str:
        """
        Summarise total spending grouped by category.

        Args:
            phone: The user's WhatsApp phone number.

        Returns:
            A breakdown of expenses by category, or a message if no expenses exist.
        """
        logger.info("get_spending_by_category called → phone=%s", phone)
        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                stmt = select(Transaction).where(
                    Transaction.user_id == user.id,
                    Transaction.type == TransactionType.EXPENSE,
                )
                expenses = session.exec(stmt).all()

                if not expenses:
                    logger.info("No expenses found for %s", phone)
                    return "No expenses recorded yet."

                totals: dict[str, Decimal] = {}
                for tx in expenses:
                    totals[tx.category] = totals.get(tx.category, Decimal("0")) + tx.amount

                logger.info(
                    "Spending by category for %s → %s",
                    phone,
                    {k: float(v) for k, v in totals.items()},
                )

                lines = [f"📂 {cat}: ₹{amt}" for cat, amt in sorted(totals.items())]
                return "Spending by category:\n" + "\n".join(lines)
        except Exception as e:
            logger.exception("get_spending_by_category failed")
            return f"Error fetching category data: {e}"

    def get_spending_by_date(
        self,
        phone: str,
        start_date: str,
        end_date: str = "",
    ) -> str:
        """
        Get a day-by-day spending breakdown for a date range.

        Args:
            phone: The user's WhatsApp phone number.
            start_date: Start date in YYYY-MM-DD format (e.g. '2026-03-01').
            end_date: End date in YYYY-MM-DD format. Defaults to today if omitted.

        Returns:
            A date-wise breakdown of expenses with daily totals and a grand total.
        """
        logger.info(
            "get_spending_by_date called → phone=%s start=%s end=%s",
            phone, start_date, end_date,
        )

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            return f"Invalid start_date '{start_date}'. Use YYYY-MM-DD format."

        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.utcnow()
        except ValueError:
            return f"Invalid end_date '{end_date}'. Use YYYY-MM-DD format."

        end = end.replace(hour=23, minute=59, second=59)

        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                stmt = select(Transaction).where(
                    Transaction.user_id == user.id,
                    Transaction.type == TransactionType.EXPENSE,
                    Transaction.timestamp >= start,
                    Transaction.timestamp <= end,
                )
                expenses = session.exec(stmt).all()

                if not expenses:
                    logger.info("No expenses in date range for %s", phone)
                    return f"No expenses found between {start_date} and {end.strftime('%Y-%m-%d')}."

                daily: dict[date, list[Transaction]] = {}
                for tx in expenses:
                    day = tx.timestamp.date()
                    daily.setdefault(day, []).append(tx)

                grand_total = Decimal("0")
                lines: list[str] = []

                for day in sorted(daily.keys()):
                    day_txs = daily[day]
                    day_total = sum(tx.amount for tx in day_txs)
                    grand_total += day_total

                    lines.append(f"\n📅 {day.strftime('%a, %d %b %Y')} — ₹{day_total}")
                    for tx in day_txs:
                        lines.append(f"   • ₹{tx.amount} [{tx.category}] {tx.description}")

                lines.append(f"\n💸 Total: ₹{grand_total}")

                logger.info(
                    "Date-wise spending for %s → %d days, total=₹%s",
                    phone, len(daily), grand_total,
                )
                return "\n".join(lines)
        except Exception as e:
            logger.exception("get_spending_by_date failed")
            return f"Error fetching date-wise spending: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# AssistantTools — Task Management & Health Tracking
# ═══════════════════════════════════════════════════════════════════════════════

class AssistantTools(Toolkit):
    def __init__(self) -> None:
        tools = [
            self.get_current_datetime,
            self.add_task,
            self.get_tasks,
            self.update_task_status,
            self.log_health_metric,
            self.get_health_summary,
        ]
        super().__init__(name="assistant_tools", tools=tools)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_or_create_user(self, session: Session, phone: str) -> User:
        """Look up a user by phone; create a new row on first contact."""
        stmt = select(User).where(User.phone_number == phone)
        user = session.exec(stmt).first()
        if not user:
            logger.info("First-time user, creating record for %s", phone)
            user = User(phone_number=phone)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    # ── Utility tools ────────────────────────────────────────────────────────

    def get_current_datetime(self) -> str:
        """
        Get the current date and time in IST (Indian Standard Time).

        Returns:
            A string with today's date, day of the week, and the current time.
        """
        now_utc = datetime.utcnow()
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        logger.info("get_current_datetime called → %s IST", now_ist)
        return (
            f"📅 Aaj: {now_ist.strftime('%A, %d %B %Y')}\n"
            f"🕐 Time: {now_ist.strftime('%I:%M %p')} IST"
        )

    # ── Task Management tools ────────────────────────────────────────────────

    def add_task(
        self,
        phone: str,
        task_desc: str,
        due_date: str = "",
    ) -> str:
        """
        Save a new task or reminder for the user.

        Args:
            phone: The user's WhatsApp phone number (e.g. 'whatsapp:+1234567890').
            task_desc: A short description of the task (e.g. 'Buy groceries').
            due_date: Optional due date in YYYY-MM-DD or YYYY-MM-DD HH:MM format.

        Returns:
            A confirmation message with the saved task details.
        """
        logger.info(
            "add_task called → phone=%s desc=%r due=%s",
            phone, task_desc, due_date,
        )

        parsed_due: datetime | None = None
        if due_date:
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    parsed_due = datetime.strptime(due_date, fmt)
                    break
                except ValueError:
                    continue
            if parsed_due is None:
                logger.warning("Invalid due_date format: %r", due_date)
                return (
                    f"Yaar, ye date format samajh nahi aaya: '{due_date}'. "
                    "YYYY-MM-DD ya YYYY-MM-DD HH:MM mein bhejo."
                )

        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                task = Task(
                    user_id=user.id,  # type: ignore[arg-type]
                    description=task_desc,
                    due_date=parsed_due,
                )
                session.add(task)
                session.commit()
                session.refresh(task)

                due_str = (
                    f" (Due: {parsed_due:%d %b %Y, %I:%M %p})"
                    if parsed_due
                    else ""
                )
                msg = f"✅ Task saved: '{task.description}'{due_str}"
                logger.info("Task saved: id=%s %s", task.id, msg)
                return msg
        except Exception as e:
            logger.exception("add_task failed")
            return f"Error saving task: {e}"

    def get_tasks(self, phone: str, status: str = "pending") -> str:
        """
        Retrieve tasks for the user filtered by status.

        Args:
            phone: The user's WhatsApp phone number.
            status: Filter by task status — 'pending', 'completed', or 'all'.

        Returns:
            A formatted list of matching tasks, or a message if none exist.
        """
        logger.info("get_tasks called → phone=%s status=%s", phone, status)
        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                stmt = select(Task).where(Task.user_id == user.id)

                if status.lower() != "all":
                    stmt = stmt.where(Task.status == status.lower())

                stmt = stmt.order_by(Task.created_at.desc())  # type: ignore[union-attr]
                tasks = session.exec(stmt).all()

                if not tasks:
                    logger.info("No tasks found for %s (status=%s)", phone, status)
                    return (
                        "Koi task nahi mila! Chill ho kya? 😎 "
                        "Naya task add karna ho toh bata."
                    )

                lines: list[str] = []
                for t in tasks:
                    icon = "✅" if t.status == "completed" else "📌"
                    due_part = f" | Due: {t.due_date:%d %b}" if t.due_date else ""
                    lines.append(f"{icon} [#{t.id}] {t.description}{due_part}")

                logger.info("Returning %d tasks for %s", len(lines), phone)
                return f"Tasks ({status}):\n" + "\n".join(lines)
        except Exception as e:
            logger.exception("get_tasks failed")
            return f"Error fetching tasks: {e}"

    def update_task_status(
        self,
        phone: str,
        task_id: int,
        status: str,
    ) -> str:
        """
        Update the status of an existing task (e.g. mark as 'completed').

        Args:
            phone: The user's WhatsApp phone number.
            task_id: The numeric ID of the task to update.
            status: New status value — typically 'completed' or 'pending'.

        Returns:
            A confirmation message, or an error if the task was not found.
        """
        logger.info(
            "update_task_status called → phone=%s task_id=%s status=%s",
            phone, task_id, status,
        )
        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                stmt = select(Task).where(
                    Task.id == task_id,
                    Task.user_id == user.id,
                )
                task = session.exec(stmt).first()

                if not task:
                    logger.warning("Task #%s not found for %s", task_id, phone)
                    return f"Task #{task_id} nahi mila, bhai. ID check kar le ek baar."

                old_status = task.status
                task.status = status.lower()
                session.add(task)
                session.commit()

                logger.info(
                    "Task #%s status changed: %s → %s", task_id, old_status, status,
                )
                if status.lower() == "completed":
                    return f"🎉 Shabaash! Task #{task_id} ('{task.description}') done mark kar diya!"
                return f"Task #{task_id} ka status '{status}' kar diya hai."
        except Exception as e:
            logger.exception("update_task_status failed")
            return f"Error updating task: {e}"

    # ── Health Tracking tools ────────────────────────────────────────────────

    def log_health_metric(
        self,
        phone: str,
        metric_type: str,
        value: float,
        unit: str = "ml",
    ) -> str:
        """
        Log a health metric entry for the user (e.g. water intake, steps).

        Args:
            phone: The user's WhatsApp phone number.
            metric_type: Type of metric — e.g. 'water', 'steps', 'sleep'.
            value: Numeric value of the metric (e.g. 500 for 500 ml of water).
            unit: Unit of measurement (default 'ml'). Examples: 'ml', 'steps', 'hours'.

        Returns:
            A confirmation message with the logged metric details.
        """
        logger.info(
            "log_health_metric called → phone=%s type=%s value=%s unit=%s",
            phone, metric_type, value, unit,
        )
        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                entry = HealthLog(
                    user_id=user.id,  # type: ignore[arg-type]
                    metric_type=metric_type.lower(),
                    value=value,
                    unit=unit.lower(),
                )
                session.add(entry)
                session.commit()
                session.refresh(entry)

                logger.info("HealthLog saved: id=%s %s=%s%s", entry.id, metric_type, value, unit)

                if metric_type.lower() == "water":
                    return (
                        f"💧 Nice! {value} {unit} paani log kar diya. "
                        "Hydrated raho, boss! 💪"
                    )
                return f"✅ Logged: {metric_type} → {value} {unit}."
        except Exception as e:
            logger.exception("log_health_metric failed")
            return f"Error logging health metric: {e}"

    def get_health_summary(
        self,
        phone: str,
        metric_type: str,
        days: int = 1,
    ) -> str:
        """
        Get the aggregate total of a health metric over the last N days.

        Args:
            phone: The user's WhatsApp phone number.
            metric_type: Type of metric to summarise — e.g. 'water', 'steps'.
            days: Number of days to look back (default 1 = today only).

        Returns:
            The summed total for the requested metric over the given period.
        """
        logger.info(
            "get_health_summary called → phone=%s type=%s days=%d",
            phone, metric_type, days,
        )
        try:
            with Session(engine) as session:
                user = self._get_or_create_user(session, phone)
                cutoff = datetime.utcnow() - timedelta(days=days)

                stmt = select(HealthLog).where(
                    HealthLog.user_id == user.id,
                    HealthLog.metric_type == metric_type.lower(),
                    HealthLog.logged_at >= cutoff,
                )
                logs = session.exec(stmt).all()

                if not logs:
                    logger.info("No %s logs for %s in last %d day(s)", metric_type, phone, days)
                    if metric_type.lower() == "water":
                        return (
                            f"Aaj ka paani ka record nahi hai! 💧 "
                            "Ek glass pee ke bata, main log kar dunga."
                        )
                    return f"No '{metric_type}' data found for the last {days} day(s)."

                total = sum(log.value for log in logs)
                unit = logs[0].unit
                count = len(logs)
                period = "aaj" if days == 1 else f"last {days} days"

                logger.info(
                    "Health summary for %s → %s: %.1f %s (%d entries, %s)",
                    phone, metric_type, total, unit, count, period,
                )

                if metric_type.lower() == "water":
                    goal = 3000.0
                    remaining = max(goal - total, 0)
                    pct = min(total / goal * 100, 100)
                    return (
                        f"💧 Paani tracker ({period}):\n"
                        f"   Total: {total:.0f} {unit} / {goal:.0f} {unit} ({pct:.0f}%)\n"
                        f"   Baaki: {remaining:.0f} {unit}\n"
                        f"   Entries: {count}"
                    )
                return (
                    f"📊 {metric_type.capitalize()} summary ({period}):\n"
                    f"   Total: {total:.1f} {unit}\n"
                    f"   Entries: {count}"
                )
        except Exception as e:
            logger.exception("get_health_summary failed")
            return f"Error fetching health summary: {e}"
