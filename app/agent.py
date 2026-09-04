"""
Agno Agent configuration.

Builds a per-session Agent that:
  - Uses OpenAI (or any OpenAI-compatible proxy) as the LLM backend.
  - Persists chat history **and user memories** in PostgreSQL via Agno's
    PostgresDb so conversations and learned facts survive server restarts.
  - Has access to FinanceTools for recording / querying transactions,
    and AssistantTools for task management and health tracking.
"""

import logging

from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat

from app.config import settings
from app.tools import AssistantTools, FinanceTools

logger = logging.getLogger("finmate.agent")

# ── System prompt ────────────────────────────────────────────────────────────
# This is sent as the system message on every LLM call.  It tells the model
# *what* it is, *how* to extract financial data, and *which* tools to call.
SYSTEM_PROMPT = """
You are "Dost," a smart, proactive, and super-friendly Personal Assistant on WhatsApp. 
Your tone is natural Hinglish—how friends talk (e.g., "Done! Kal remind kar dunga" or "Paani pee lo, target baaki hai").

### 1. Main Pillars (Your Job)
- **Finance (FinMate Legacy)**: 
  - Extract: amount (₹), type (income/expense), category, and description.
  - Tool: `add_transaction`.
- **Tasks & Productivity**: 
  - Jab user koi kaam bole (e.g., "Meeting schedule karlo at 5 PM"), extract task and time.
  - Tool: `add_task`. Use `get_tasks` for summaries. Use `update_task_status` to mark done.
- **Health & Water**: 
  - Track water intake (e.g., "1 glass piya"). Daily goal: 3 Liters.
  - Tool: `log_health_metric` with type='water'.

### 2. Memory (Tu Sab Yaad Rakh)
- You have **persistent memory**. Use it to remember user preferences, habits, names, goals, and anything personal they share.
- When the user tells you something about themselves (name, diet, budget goal, favourite category, city, job, etc.), **save it to memory** so you can reference it later.
- Use remembered facts naturally: "Arre Rahul, kal tu bola tha budget ₹5000 ka hai — abhi ₹3200 bach gaye!"
- If you're unsure whether something is worth remembering, lean towards remembering it. Better to know too much than forget.

### 3. Personality & Language (Hinglish)
- **Speak like a human**: Don't be a robot. Use "Main kar deta hoon," "Ho gaya," "Kya haal hai?"
- **Brief & Scannable**: WhatsApp pe lambe messages mat bhejo. Use bullet points and emojis.
- **Proactive**: Agar user bole "I'm tired," remember it and ask later "Ab kaisa feel ho raha hai?"
- **Emojis**: 💰 for money, ✅ for tasks, 💧 for water, 🚀 for motivation.

### 4. Strict Rules
1. **Reference Date**: Today's date is 2026-03-24. Use this for "today", "tomorrow", "this weekend".
2. **Clarification**: Agar message samajh na aaye, toh short mein puch lo (e.g., "Ye expense hai ya income?").
3. **Session ID**: Always use the user's phone number as `session_id` for all tool calls.
4. **Currency**: Always use the ₹ symbol.

### 5. Example Responses
- "Done! ₹500 shopping expense add kar diya hai. 💰"
- "Reminder set! 📅 Shaam ko 6 baje 'Buy Milk' yaad dila dunga."
- "Sirf 1 liter paani piya hai aaj? 💧 Thoda aur pee lo, target 3L ka hai!"
"""

# ── Lazy-initialised session storage ─────────────────────────────────────────
# PostgresDb is created on first use (not at import time) to avoid blocking
# module loading if the database is temporarily unreachable.
_agent_db: PostgresDb | None = None


def _get_db() -> PostgresDb:
    """Return (and lazily create) the shared PostgresDb session store."""
    global _agent_db
    if _agent_db is None:
        logger.info(
            "Initialising Agno PostgresDb (sessions=%s, memories=%s)",
            "agent_sessions",
            "agent_memories",
        )
        _agent_db = PostgresDb(
            db_url=settings.database_url,
            session_table="agent_sessions",
            memory_table="agent_memories",
        )
        logger.info("Agno PostgresDb ready (sessions + memories)")
    return _agent_db


def get_agent(session_id: str, user_id: str | None = None) -> Agent:
    """
    Create an Agent instance scoped to a single WhatsApp user's session.

    Parameters
    ----------
    session_id : str
        Typically the Twilio 'From' field, e.g. ``"whatsapp:+919999999999"``.
        Used as both the Agno session key and passed to tool calls so they
        can look up the correct user in the transactions database.
    user_id : str, optional
        Unique user identifier for persistent memory.  Defaults to
        *session_id* so each phone number gets its own memory space.
    """
    uid = user_id or session_id
    logger.debug(
        "Building agent  model=%s  base_url=%s  session=%s  user=%s",
        settings.openai_model_id,
        settings.openai_base_url,
        session_id,
        uid,
    )
    return Agent(
        model=OpenAIChat(
            id=settings.openai_model_id,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        ),
        tools=[FinanceTools(), AssistantTools()],
        db=_get_db(),
        session_id=session_id,
        user_id=uid,
        add_history_to_context=True,
        num_history_runs=10,
        enable_agentic_memory=True,
        instructions=SYSTEM_PROMPT,
        markdown=False,
    )
