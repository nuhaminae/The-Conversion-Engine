# The-Conversion-Engine

[![CI](https://github.com/nuhaminae/The-Conversion-Engine/actions/workflows/ci.yml/badge.svg)](https://github.com/nuhaminae/The-Conversion-Engine/actions/workflows/ci.yml)
![Black Formatting](https://img.shields.io/badge/code%20style-black-000000.svg)
![isort Imports](https://img.shields.io/badge/imports-isort-blue.svg)
![Flake8 Lint](https://img.shields.io/badge/lint-flake8-yellow.svg)

---

## Project Overview

The **Conversion Engine** is a multi-layered automation system designed to handle the full lifecycle of B2B lead development from initial discovery and deep research-driven enrichment to multi-channel outreach and final meeting booking.

---

### The conversion engine architectural design

Below is the detailed system architecture in Mermaid format, reflecting the core components described across the sources:

```mermaid
graph TD
    %% Lead Discovery & Input Layer
    subgraph Lead_Discovery [Input Layer]
        A1[Website Inbound Form] -->|Webhooks| B
        A2[Crunchbase Outbound List] -->|Batch/Stream| B
        A3[Partner Referral Stream] -->|API| B
    end

    %% Enrichment Pipeline
    subgraph Enrichment_Pipeline [Enrichment & Signal Intelligence]
        B[Central Orchestrator] --> C1[Crunchbase ODM: Firmographics]
        B --> C2[CFPB Database: Regulatory Exposure - Acme]
        B --> C3[Hiring Signal Brief: Funding/Layoffs/Job Posts - Tenacious]
        B --> C4[Playwright: News/Web Scraping]
        
        C1 & C2 & C3 & C4 --> D[Brief Generator]
        D -->|Enrichment Brief| E1[Firmographic Record]
        D -->|Compliance Brief| E2[Regulatory Note]
        D -->|Competitive Gap Brief| E3[AI Maturity Score]
    end

    %% Agent Core
    subgraph Agent_Brain [LLM Agent Core]
        F[LLM Agent: Backbone Claude/GPT/Qwen]
        E1 & E2 & E3 -->|Context Injection| F
        F --> G{Conversation Logic}
        G -->|Tool Calling| H1[HubSpot MCP Server]
        G -->|Scheduling| H2[Cal.com API]
    end

    %% Communication Channels
    subgraph Communication_Channels [Outbound/Inbound Channels]
        G -->|Email Primary - Tenacious| I1[Resend / MailerSend]
        G -->|SMS Primary - Acme / Scheduling| I2[Africa's Talking Sandbox]
        G -->|Voice Bonus| I3[Shared Voice Rig / Webhook Gateway]
    end

    %% Systems of Record
    subgraph Systems_of_Record [Downstream Integration]
        H1 --> J1[(HubSpot CRM)]
        H2 --> J2[(SDR Calendar)]
        I1 & I2 & I3 --> K[Prospect Interaction]
    end

    %% Observability & Eval
    subgraph Quality_Control [Observability & Evaluation]
        F & G & H1 --> L[Langfuse: Traces & Cost Attribution]
        L --> M[Evidence Graph Validation]
        M --> N[tau2-Bench: Ground-Truth Eval]
    end

    %% Feedback Loop
    K -->|Replies| B
```

---

### Core Architectural Components

- **Enrichment Pipeline:** This layer is critical for moving beyond generic outreach. For Acme ComplianceOS, it identifies **regulatory exposure** via the CFPB database. For Tenacious, it generates a **hiring signal brief** and **competitor gap brief**, scoring prospects on **AI maturity** (0–3 scale) to tailor the pitch.
- **LLM Agent Core:** The "brain" of the system uses a development-tier LLM (like Qwen or DeepSeek) for iteration and an evaluation-tier (Claude or GPT-5) for high-stakes interactions. It operates through **dual-control coordination**, waiting for user input or taking tool actions as required.
- **Channel Priority:** The architecture adapts to the target segment. In the compliance version, **SMS** is the primary driver for "speed-to-lead". In the Tenacious version, **Email** is primary for professional outreach to executives, while SMS is reserved for warm-lead scheduling.
- **HubSpot MCP Integration:** The system uses a **Model Context Protocol (MCP)** server to allow the agent to read and write directly to HubSpot, ensuring all interactions, transcripts, and firmographic data are structured as a record of truth.
- **Observability & Validation:** **Langfuse** captures every trace, tool call, and token cost. This data feeds into an **Evidence-Graph**, which maps every claim (e.g., "cost per qualified lead") back to a specific trace file for auditability.


---

- [The-Conversion-Engine](#the-conversion-engine)
  - [Project Overview](#project-overview)
    - [The conversion engine architectural design](#the-conversion-engine-architectural-design)
    - [Core Architectural Components](#core-architectural-components)
  - [Project Structure (Snippet)](#project-structure-snippet)
  - [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [Setup](#setup)
    - [Deploying to Render](#deploying-to-render)
    - [Setting up Webhooks](#setting-up-webhooks)
  - [Usage](#usage)
  - [Setup proofs](#setup-proofs)
  - [Project Status](#project-status)

---

## Project Structure (Snippet)

```bash
The-Conversion-Engine/ 
├── conversion_engine.py/ 
│   ├── __init__.py                       
│   └── main.py                 # FastAPI integration 
├── evaluation                       
│   ├── baseline.md
│   ├── score_log.json
│   └── trace_log.jsnol
└── DOMAIN_NOTES.md 
```

---

## Installation

### Prerequisites

- Python 3.12  
- Git  
- Docker (for local Cal.com testing)  
- Render account (free tier is sufficient)
- Hubspot account
  
---

### Setup

```bash
git clone https://github.com/nuhaminae/The-Conversion-Engine.git
cd The-Conversion-Engine
uv sync   # recommended dependency management
```

---

### Deploying to Render

1. **Create a Render account**  
   Sign up at [render.com](https://render.com) (no credit card required).

2. **Provision a Web Service**  
   - Click **New → Web Service**.  
   - Connect your GitHub repo (`The-Conversion-Engine`).  
   - Select branch `main`.  
   - Environment: Python 3.12.  

    ```bash
    #Build command: 
    poetry install

    #Start command:  
    poetry run uvicorn conversion_engine_backend.main:app --host 0.0.0.0 --port $PORT
    ```

3. **Verify Deployment**  
   After build completes, Render will give you a public URL like:  

   ```bash
   https://the-conversion-engine.onrender.com
   ```  

   Visit it in your browser. You should see:  

   ```json
   {"status":"ok","message":"FastAPI is running on Render"}
   ```

---

### Setting up Webhooks

Use the Render public URL. For example:

- **Africa’s Talking Sandbox → SMS Callback URL**  
- **Resend / MailerSend → Reply Webhook URL**
- **HubSpot MCP → Conversation Events Webhook URL**  
- **Cal.com → Booking Events Webhook URL**
  
``` bash
https://the-conversion-engine.onrender.com/webhook
```

---

## Usage

1. Send message to short number created in Africa's Talking. Make sure webhook is set in `Callback URLs`. It is sucessful when you get an email in your inbox set in the env.

2. To create contact in hubspot, run:

``` bash
https://the-conversion-engine.onrender.com/create-test-contact
```

If sucessful you will see, example:

```json
{
  "status": "success",
  "contact_id": "763259095241"
}
```

3. Clone and setup `Cal.com`

```bash
# Verify docker is installed
docker --version
docker compose version

# Clone cal.com
git clone https://github.com/calcom/cal.com.git
cd cal.com

# Execute the cloned file
docker compose up

```

---

## Setup proofs

![Africa's Talking](screengrabs/AfricasTalking_screencap.png)

![Hubspot](screengrabs/Hubspot_screencap.png)

![Resend](screengrabs/Resend_screengrab.png)

---

## Project Status

The project is underway, check the [commit history](https://github.com/nuhaminae/The-Conversion-Engine/) for updates.

- **webhook.log**  
  Contains at least two entries: one SMS webhook trace and one HubSpot contact creation trace. These demonstrate end‑to‑end observability through Langfuse.

- **score_log.json**  
  References the program‑provided baseline run using `openrouter/qwen/qwen3-next-80b-a3b-thinking`. No reproduction required; one trial is sufficient.

- **baseline.md**  
  Summarises the baseline (provided), current stack setup (Render, Africa’s Talking, HubSpot, Langfuse), and confidence in traces. Cal.com setup is in progress.

- [x] Render backend deployed and reachable at public URL.  
- [x] Africa’s Talking sandbox provisioned, SMS webhook tested.  
- [x] HubSpot Developer Sandbox provisioned, test contact created.  
- [x] Langfuse cloud project created, test trace visible.  
- [x] Cal.com cloning in progress (Docker Compose setup).  
- [x] OpenRouter API key configured, ready for enrichment/qualification logic.  

Budget usage: all free tiers so far; $10 allocation remains intact.
