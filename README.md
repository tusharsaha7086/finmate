# FinMate (Dost) 🤖💰

> **Autonomous AI-Powered Financial & Lifestyle Companion on WhatsApp**  
> *Built with FastAPI, Agno (Phidata), SQLModel, PostgreSQL, and Twilio.*

---

## 📖 Overview

**FinMate** (persona: **"Dost"**) is an autonomous conversational AI agent living inside WhatsApp that simplifies personal finance, daily productivity, and health tracking. Instead of forcing users into clunky spreadsheets or complex budgeting apps, FinMate allows users to manage their life through effortless, natural conversation in **Hinglish** and **English**.

FinMate doesn't just passively answer questions—it is proactive. It maintains long-term **persistent memory** of user preferences and habits, executes database-backed queries for financial reporting, and uses a background scheduler to send timely task nudges and hydration reminders directly to WhatsApp.

---

## ✨ Key Pillars & Features

### 1. 💰 Smart Financial Management (FinMate Legacy)
- **Natural Language Transaction Logging**: Text expenses and income naturally (e.g., *"Aaj lunch pe 350 kharch hue"* or *"Salary received 75000"*).
- **Automated Categorization**: Automatically infers categories (Food, Travel, Utilities, Shopping, Salary, etc.) and descriptions.
- **Balance & Cash Flow**: Calculates live net balance, total income, and total expenses.
- **Spending Analytics & Ledger**:
  - Recent transaction history with chronological audit trails.
  - Category-wise spending breakdowns.
  - Date-range and day-by-day expense analysis with daily subtotals.

### 2. 📌 Productivity & Task Management
- **Conversational Task Creation**: Add to-dos and reminders with flexible datetime understanding (e.g., *"Remind me to call client tomorrow at 4 PM"*).
- **Status Tracking**: Filter tasks by `pending` or `completed` status.
- **Natural Status Updates**: Mark items complete with natural text (e.g., *"Task #2 done"*).

### 3. 💧 Health & Hydration Tracking
- **Water Intake Logging**: Log water consumption in milliliters or glasses (e.g., *"2 glass paani piya"*).
- **Progress Towards Daily Goals**: Real-time tracking against a 3,000 ml daily hydration goal.
- **Historical Summaries**: View logs and progress over customized time windows (today, last 7 days).

### 4. 🧠 Persistent Agentic Memory
- **Long-Term Memory**: Powered by Agno's `PostgresDb`, memories and conversation context persist across server restarts.
- **Personalized Context**: Remembers user names, recurring expenses, budget targets, habits, and preferences, allowing the agent to reference past conversations naturally.

### 5. ⏰ Proactive Background Automations (APScheduler)
- **Task Reminders Engine**: An automated background job scans for pending tasks due within a 5-minute window and dispatches proactive WhatsApp reminders.
- **Hydration Nudges**: Periodic cron reminders (9:00 AM, 12:00 PM, 3:00 PM, 6:00 PM, 9:00 PM IST) to keep users on track with their wellness goals.

---

## 🏗️ Architecture & Data Flow

```mermaid
flowchart TD
    subgraph User["User Touchpoint"]
        WA[WhatsApp User]
    end

    subgraph TwilioCloud["Twilio Infrastructure"]
        TWH[Twilio WhatsApp Gateway / Webhook]
        TREST[Twilio REST API Client]
    end

    subgraph Backend["FastAPI Backend (FinMate)"]
        EP["/webhook (HTTP POST)"]
        TPE[ThreadPoolExecutor]
        Agent[Agno AI Agent 'Dost']
        LLM[OpenAI / Gemini / Proxy LLM]
        
        subgraph Toolkits["Agno Toolkits"]
            FT[FinanceTools]
            AT[AssistantTools]
        end

        SCHED[APScheduler Background Engine]
    end

    subgraph Storage["PostgreSQL Database (Supabase / Local)"]
        T_USERS[(users)]
        T_TX[(transactions)]
        T_TASKS[(tasks)]
        T_HEALTH[(health_logs)]
        T_SESSIONS[(agent_sessions)]
        T_MEMORIES[(agent_memories)]
        T_JOBS[(apscheduler_jobs)]
    end

    %% Inbound Flow
    WA -->|Message| TWH
    TWH -->|Form Payload| EP
    EP -->|Offload Sync Call| TPE
    TPE --> Agent
    Agent <-->|Inference| LLM
    Agent --> FT
    Agent --> AT
    FT <--> T_TX
    FT <--> T_USERS
    AT <--> T_TASKS
    AT <--> T_HEALTH
    Agent <--> T_SESSIONS
    Agent <--> T_MEMORIES
    Agent -->|Response Text| EP
    EP -->|TwiML XML| TWH
    TWH -->|WhatsApp Reply| WA

    %% Outbound Proactive Flow
    SCHED -.->|Check due tasks & water nudges| T_TASKS
    SCHED -->|Send Outbound Alert| TREST
    TREST -->|Direct Message| WA
```

---

## 🗄️ Database Schema

FinMate uses **SQLModel** (SQLAlchemy 2.x) to manage tables alongside Agno's internal tables:

```mermaid
erDiagram
    users ||--o{ transactions : logs
    users ||--o{ tasks : creates
    users ||--o{ health_logs : tracks

    users {
        int id PK
        string phone_number UK "Indexed WhatsApp ID"
        datetime created_at
    }

    transactions {
        int id PK
        int user_id FK
        decimal amount "Numeric(12,2)"
        string type "income | expense"
        string category "e.g. food, salary"
        string description
        datetime timestamp
    }

    tasks {
        int id PK
        int user_id FK
        string description
        datetime due_date
        string status "pending | completed"
        boolean reminder_sent
        datetime created_at
    }

    health_logs {
        int id PK
        int user_id FK
        string metric_type "water, steps, etc."
        float value
        string unit "ml, steps, etc."
        datetime logged_at
    }
```

*Note: In addition to the application tables above, Agno automatically manages `agent_sessions` and `agent_memories`, while APScheduler manages `apscheduler_jobs` in PostgreSQL.*

---

## 📁 Project Structure

```text
finmate/
├── app/
│   ├── __init__.py
│   ├── agent.py          # Agno Agent definition, system prompt, and session memory configuration
│   ├── config.py         # Pydantic Settings reading .env variables
│   ├── database.py       # SQLModel engine initialization & session generator
│   ├── main.py           # FastAPI application, lifespan manager, and /webhook endpoint
│   ├── models.py         # SQLModel database schemas (User, Transaction, Task, HealthLog)
│   ├── scheduler.py      # APScheduler recurring jobs (due tasks & water intake nudges)
│   └── tools.py          # Agno Toolkits (FinanceTools & AssistantTools) with CRUD logic
├── .env.example          # Environment variable template
├── requirements.txt      # Python package dependencies
└── README.md             # Project documentation
```

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **API Framework** | [FastAPI](https://fastapi.tiangolo.com/) | High-performance asynchronous REST API handling webhooks |
| **Agentic Framework** | [Agno](https://github.com/agno-agi/agno) | Multi-agent orchestration, persistent memory, and tool routing |
| **Database & ORM** | [PostgreSQL](https://www.postgresql.org/) + [SQLModel](https://sqlmodel.tiangolo.com/) | Type-safe database modeling with SQLAlchemy and Pydantic |
| **LLM Provider** | OpenAI (`gpt-4o`) / Gemini (`gemini-2.0-flash`) | Natural language understanding, function calling, Hinglish persona |
| **Messaging API** | [Twilio](https://www.twilio.com/docs/whatsapp) | WhatsApp webhook ingestion (TwiML) & outbound notifications |
| **Task Scheduler** | [APScheduler](https://apscheduler.readthedocs.io/) | Background job scheduling backed by SQLAlchemy job store |
| **Concurrency** | `ThreadPoolExecutor` | Prevents sync LLM/DB agent operations from blocking the async loop |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python**: Version 3.11 or higher
- **PostgreSQL**: Local instance or cloud database (e.g., [Supabase](https://supabase.com/), Neon)
- **Twilio Account**: With WhatsApp Sandbox enabled ([Twilio Console](https://console.twilio.com/))
- **LLM API Key**: OpenAI API Key, OpenAI-compatible proxy, or Google Gemini API Key
- **Tunneling Tool**: [ngrok](https://ngrok.com/) or Cloudflare Tunnel for exposing local webhook to Twilio

---

### 2. Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/tusharsaha7086/finmate.git
   cd finmate
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Environment Variables**:
   Copy the example file and update with your credentials:
   ```bash
   cp .env.example .env
   ```

   Fill in `.env`:
   ```env
   # PostgreSQL Connection
   DATABASE_URL=postgresql://postgres:password@localhost:5432/finmate

   # LLM Backend
   OPENAI_API_KEY=your_openai_api_key_or_proxy_key
   OPENAI_MODEL_ID=gpt-4o
   OPENAI_BASE_URL=https://api.openai.com/v1

   # Twilio Configuration
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=+14155238886
   ```

---

### 3. Running the Server

Start the FastAPI application with Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Upon startup:
- SQLModel verifies and creates database tables (`users`, `transactions`, `tasks`, `health_logs`).
- Agno initializes `agent_sessions` and `agent_memories`.
- APScheduler initializes the background jobs with the PostgreSQL jobstore.

You can verify server health at:
```text
http://localhost:8000/health
```

---

### 4. Connecting Twilio WhatsApp Sandbox

1. In a separate terminal, expose port 8000:
   ```bash
   ngrok http 8000
   ```
2. Copy your forwarding HTTPS URL (e.g., `https://abcdef.ngrok-free.app`).
3. Navigate to **Twilio Console** > **Messaging** > **Try it out** > **Send a WhatsApp message** > **Sandbox Settings**.
4. Set **"WHEN A MESSAGE COMES IN"** to:
   ```text
   https://abcdef.ngrok-free.app/webhook
   ```
   *(Ensure HTTP Method is set to **HTTP POST**)*.
5. Save the configuration. Join the sandbox from your WhatsApp using the join code provided by Twilio.

---

## 💬 Sample WhatsApp Conversations

### Recording Expenses & Querying Balance
```text
User:     Bhai, lunch me 450 aur cab me 180 kharch ho gaye.
FinMate:  Done! Dono expenses add kar diye:
          • ₹450 [food] lunch
          • ₹180 [travel] cab
          Total: ₹630 💸

User:     Mera abhi ka total balance aur kharche bata de.
FinMate:  Ye raha tera hisaab-kitaab:
          💰 Income: ₹50,000
          💸 Expenses: ₹14,200
          📊 Balance: ₹35,800
```

### Date-wise & Category-wise Breakdown
```text
User:     Mera category wise kharcha dikha.
FinMate:  Spending by category:
          📂 food: ₹5,400
          📂 travel: ₹2,300
          📂 utilities: ₹1,500
          📂 shopping: ₹5,000

User:     Is hafte ka spending breakdown de.
FinMate:  Date-wise spending:
          📅 Mon, 02 Mar 2026 — ₹750
             • ₹450 [food] grocery
             • ₹300 [travel] auto
          📅 Tue, 03 Mar 2026 — ₹1,200
             • ₹1,200 [shopping] shoes
          💸 Total: ₹1,950
```

### Task Scheduling & Proactive Reminders
```text
User:     Kal subah 10:30 baje mom ko call karne ka reminder daal de.
FinMate:  ✅ Task saved: 'Call mom' (Due: 25 Mar 2026, 10:30 AM)
          Waqt pe yaad dila dunga! 📅

[At 10:25 AM - Automated Proactive Alert]
FinMate:  ⏰ Dost, reminder! Aapka task 'Call mom' pending hai. Abhi kar lo! ✅
```

### Health & Hydration Tracking
```text
User:     2 glass paani piya abhi.
FinMate:  💧 Nice! 500 ml paani log kar diya. Hydrated raho, boss! 💪

User:     Aaj ka paani ka status kya hai?
FinMate:  💧 Paani tracker (aaj):
             Total: 1500 ml / 3000 ml (50%)
             Baaki: 1500 ml
             Entries: 3
```

---

## 🔌 API Reference

### 1. Liveness Probe
```http
GET /health
```
**Response (`200 OK`)**:
```json
{
  "status": "ok"
}
```

### 2. Twilio Inbound Webhook
```http
POST /webhook
Content-Type: application/x-www-form-urlencoded
```
**Payload Parameters**:
- `From`: User's WhatsApp number (e.g., `whatsapp:+919876543210`)
- `Body`: The incoming message text

**Response (`200 OK`)**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>Done! ₹250 coffee expense add kar diya hai. ☕</Message>
</Response>
```

---

## 🛡️ Security & Best Practices

- **Environment Secrets**: Never commit `.env` containing sensitive database passwords or Twilio tokens to version control.
- **Webhook Validation**: In production environments, enable Twilio's X-Twilio-Signature validation in `app/main.py` using `twilio.request_validator.RequestValidator`.
- **Database Connection Pooling**: Built with SQLAlchemy connection pooling suitable for serverless and containerized deployments.

---

## 🗺️ Roadmap

- [ ] **Voice Note Support**: Ingest audio notes using OpenAI Whisper for hands-free expense tracking.
- [ ] **Receipt OCR Scanning**: Ingest photo receipts via multimodal LLMs (GPT-4o / Gemini 2.0 Flash) to automatically parse line items.
- [ ] **CSV / PDF Export**: Download monthly financial reports and statement summaries via WhatsApp media messages.
- [ ] **Multi-Currency Support**: Automatic FX conversion for international transactions.
- [ ] **Budget Alerts**: Alert users when spending exceeds 80% of defined category budgets.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
