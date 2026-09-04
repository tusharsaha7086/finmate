"""
FastAPI application entry point.

Handles Twilio WhatsApp webhook ingestion, delegates messages to the Agno
agent running in a thread-pool, and returns TwiML XML responses.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from app.agent import get_agent
from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler

# ── Logging ──────────────────────────────────────────────────────────────────
# INFO  → request lifecycle, agent milestones
# DEBUG → detailed payloads useful during local testing
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("finmate.main")

# Thread-pool so the sync agent.run() doesn't block the async event loop
executor = ThreadPoolExecutor(max_workers=4)


# ── App lifecycle ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting up — creating database tables …")
    init_db()
    logger.info("Database tables ready")

    logger.info("Starting APScheduler …")
    start_scheduler()

    yield

    logger.info("Shutting down — stopping scheduler …")
    stop_scheduler()
    logger.info("Shutting down — draining thread pool …")
    executor.shutdown(wait=False)
    logger.info("Shutdown complete")


app = FastAPI(
    title="FinMate",
    description="Autonomous WhatsApp Financial Agent",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple liveness probe — returns 200 if the server is up."""
    return {"status": "ok"}


def _run_agent(phone: str, message: str) -> str:
    """
    Synchronous wrapper executed inside the thread-pool.
    Keeps the async event loop free while the LLM round-trip happens.
    """
    start = time.perf_counter()

    logger.debug("Creating Agno agent for session=%s", phone)
    agent = get_agent(session_id=phone, user_id=phone)

    logger.info("Sending message to agent: %r", message)
    run_response = agent.run(message, user_id=phone)
    elapsed = time.perf_counter() - start

    content = run_response.content or ""
    logger.info("Agent responded in %.2fs (%d chars)", elapsed, len(content))
    logger.debug("Agent raw response: %s", content[:500])

    return content or "Sorry, I couldn't process that. Please try again."


@app.post("/webhook")
async def twilio_webhook(
    From: str = Form(...),
    Body: str = Form(...),
) -> Response:
    """
    Twilio WhatsApp webhook.

    Twilio POSTs form-encoded data with (at minimum) `From` and `Body`.
    We run the message through the Agno agent and return a TwiML
    <Response><Message>…</Message></Response> so Twilio delivers the reply.
    """
    phone = From          # e.g. "whatsapp:+919999999999"
    message = Body.strip()

    logger.info("── Incoming webhook ──────────────────────────────")
    logger.info("  From : %s", phone)
    logger.info("  Body : %s", message)

    try:
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(executor, _run_agent, phone, message)
    except Exception:
        logger.exception("Agent run failed for %s", phone)
        reply = "Something went wrong. Please try again later."

    logger.info("  Reply: %s", reply[:200])
    logger.info("──────────────────────────────────────────────────")

    # Build TwiML via Twilio SDK (handles XML escaping automatically)
    twiml = MessagingResponse()
    twiml.message(reply)

    xml_body = str(twiml)
    logger.debug("TwiML payload:\n%s", xml_body)

    return Response(content=xml_body, media_type="application/xml")
