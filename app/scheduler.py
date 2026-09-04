"""
APScheduler background jobs for proactive WhatsApp reminders.

Jobs
----
check_reminders_job       — runs every 5 min; nudges users whose tasks are due soon.
water_intake_reminder_job — runs every 3 h (9 AM – 9 PM IST); hydration nudge.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select
from twilio.rest import Client

from app.config import settings
from app.database import engine
from app.models import Task, User

logger = logging.getLogger("finmate.scheduler")

# ── Twilio client (lazy singleton) ───────────────────────────────────────────

_twilio_client: Client | None = None


def _get_twilio_client() -> Client:
    """Return (and lazily create) the shared Twilio REST client."""
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
        )
        logger.info(
            "Twilio client initialised (SID=%s…)",
            settings.twilio_account_sid[:8],
        )
    return _twilio_client


# ── Scheduler instance ───────────────────────────────────────────────────────

scheduler = BackgroundScheduler(
    jobstores={
        "default": SQLAlchemyJobStore(engine=engine),
    },
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 120,
    },
)


# ── Outbound WhatsApp helper ────────────────────────────────────────────────

def send_whatsapp_reminder(phone: str, message: str) -> None:
    """Send an outbound WhatsApp message via Twilio.

    Args:
        phone: Destination number.  Automatically prefixed with
               ``whatsapp:`` if missing.
        message: The text body to send.
    """
    if not phone.startswith("whatsapp:"):
        phone = f"whatsapp:{phone}"

    try:
        client = _get_twilio_client()
        msg = client.messages.create(
            body=message,
            from_=f"whatsapp:{settings.twilio_phone_number}",
            to=phone,
        )
        logger.info("WhatsApp sent → to=%s sid=%s", phone, msg.sid)
    except Exception:
        logger.exception("Failed to send WhatsApp message to %s", phone)


# ── Scheduled jobs ───────────────────────────────────────────────────────────

def check_reminders_job() -> None:
    """Query pending tasks due within the next 5 minutes and send reminders.

    Each task is only reminded once — the ``reminder_sent`` flag is set to
    ``True`` after a successful send so the next cycle skips it.
    """
    logger.info("⏰ check_reminders_job triggered")

    now = datetime.utcnow()
    window = now + timedelta(minutes=5)

    try:
        with Session(engine) as session:
            stmt = (
                select(Task, User)
                .join(User, Task.user_id == User.id)
                .where(
                    Task.status == "pending",
                    Task.reminder_sent == False,  # noqa: E712
                    Task.due_date.is_not(None),  # type: ignore[union-attr]
                    Task.due_date >= now,  # type: ignore[arg-type]
                    Task.due_date <= window,  # type: ignore[arg-type]
                )
            )
            results = session.exec(stmt).all()

            if not results:
                logger.info("No tasks due in the next 5 minutes")
                return

            for task, user in results:
                message = (
                    f"⏰ Dost, reminder! Aapka task '{task.description}' "
                    f"pending hai. Abhi kar lo! ✅"
                )
                send_whatsapp_reminder(user.phone_number, message)

                task.reminder_sent = True
                session.add(task)
                logger.info(
                    "Reminder sent for task #%s → %s",
                    task.id, user.phone_number,
                )

            session.commit()
            logger.info("Reminded %d task(s) this cycle", len(results))

    except Exception:
        logger.exception("check_reminders_job failed")


def water_intake_reminder_job() -> None:
    """Nudge every registered user to drink water."""
    logger.info("💧 water_intake_reminder_job triggered")

    try:
        with Session(engine) as session:
            users = session.exec(select(User)).all()

            if not users:
                logger.info("No users in the system — skipping water nudge")
                return

            message = (
                "💧 Dost, paani pee lo! Target match karna hai. "
                "Agar piya hai toh bata, main log kar dunga! 🚀"
            )

            for user in users:
                send_whatsapp_reminder(user.phone_number, message)

            logger.info("Water reminders sent to %d user(s)", len(users))

    except Exception:
        logger.exception("water_intake_reminder_job failed")


# ── Public helpers for startup / shutdown ────────────────────────────────────

def start_scheduler() -> None:
    """Register recurring jobs and start the background scheduler."""
    scheduler.add_job(
        check_reminders_job,
        "interval",
        minutes=5,
        id="check_reminders",
        replace_existing=True,
    )

    scheduler.add_job(
        water_intake_reminder_job,
        "cron",
        hour="9,12,15,18,21",
        id="water_intake_reminder",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started — jobs: %s",
        [j.id for j in scheduler.get_jobs()],
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler if it's running."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
