# Explainer — Automating Failure Attribution in Multi-Agent LLM Systems (Conversion Engine)

## The Question

The question is:
In my Week 10 Conversion Engine repo, the reply handler uses the LLM to classify a prospect reply into intents like `INTERESTED_BOOK_MEETING`, then deterministic code runs the next actions: HubSpot lookup/update, Cal.com booking-link generation, LLM reply drafting, and Resend email sending. How should I design the agent/tool-use internals so that a warm-lead scheduling path is auditable end-to-end?
This was the questio asked by my peer Nuhamin Alemayehu in simple word I put it

> How can we design a trace and evaluation system for a multi-step LLM Conversion Engine so that we can distinguish whether a scheduling failure comes from model intent classification, orchestration logic, tool execution (HubSpot/Cal/Resend), or external system/runtime issues?

This is not just a debugging question. It is an evaluation question.

In a production agent pipeline (intent → CRM → enrichment → scheduling → email), failures are compositional. A single bad outcome does not tell us *where* the system broke.

So the real problem is:

> How do we turn a linear execution pipeline into a causally attributable system?

## What the Current System Already Has

Your system already implements a working conversion pipeline:

- LLM-based intent classification (`INTERESTED_BOOK_MEETING`, etc.)
- deterministic orchestration (HubSpot → Cal → Resend)
- enrichment pipeline (CSV + scraping + scoring)
- email generation via LLM
- webhook-based reply handling

This is a valid production workflow.

However, Codex and the Who&When paper highlight a critical missing layer:

> There is no structured failure attribution system that connects outcomes to responsible components.

Currently:

- tool outputs are not typed
- failures collapse into generic errors
- logs are not step-resolved
- model decisions are not confidence-calibrated
- orchestration is hard-coded without trace metadata

So the system can execute actions, but cannot explain failures causally.

## The Core Mechanism: Failure is a Step-Level Attribution Problem

From the Who&When benchmark (multi-agent failure attribution research):

> Failure is defined as identifying both:
> 1. the responsible component (agent/tool/module)
> 2. the exact step where the failure occurred

In your system, a scheduling flow is a chain:

```text
Intent Classification
→ HubSpot Lookup/Update
→ Lead State Transition
→ Cal.com Link Generation
→ Email Drafting (LLM)
→ Email Delivery (Resend)
```

A failure can occur at any point, but without structured traces:

> all failures collapse into “booking failed”

This is equivalent to losing causal resolution in the system.

## The Core Fix: Step-Level Causal Trace Schema

The solution is to introduce a **typed execution trace per step**.

Every pipeline stage must emit:

```json
{
  "step_name": "hubspot_lookup",
  "input": {},
  "output": {},
  "status": "success|not_found|error",
  "latency_ms": 120,
  "error_type": null,
  "component": "hubspot_service"
}
```

Each request becomes a **trace graph**, not a log stream.

## Failure Attribution Layer

On top of traces, we introduce a failure classifier:

### Step 1: Model decision tracking

```json
{
  "intent": "INTERESTED_BOOK_MEETING",
  "confidence": 0.82,
  "alternatives": [
    {"label": "UNSURE", "score": 0.12},
    {"label": "NOT_INTERESTED", "score": 0.06}
  ]
}
```

This separates:

- correct classification
- low-confidence classification
- misclassification

### Step 2: Tool execution classification

Each tool returns structured outcomes:

| Tool | Possible states |
| --- | --- |
| HubSpot | success / not_found / api_error |
| Cal.com | success / invalid_slot / error |
| Resend | sent / failed / timeout |

This separates:

- missing data vs API failure vs logic failure

### Step 3: Orchestration failure detection

If:

- intent is correct
- tool succeeds
- but workflow stops

→ orchestration failure

If:

- correct tool called with wrong args

→ planning/tool-selection failure

## Unified Trace Schema (Core Artifact)

```json
{
  "trace_id": "uuid",
  "turn_id": "uuid",
  "prospect_reply": "...",

  "model_stage": {
    "intent": "INTERESTED_BOOK_MEETING",
    "confidence": 0.82,
    "prompt_version": "reply_classification_v1"
  },

  "execution_steps": [
    {
      "step": "hubspot_lookup",
      "status": "success",
      "latency_ms": 120
    },
    {
      "step": "cal_link_generation",
      "status": "success"
    },
    {
      "step": "resend_email",
      "status": "failed",
      "error_type": "timeout"
    }
  ],

  "failure_attribution": {
    "failure_stage": "tool_runtime",
    "component": "resend",
    "step": "resend_email"
  },

  "business_outcome": {
    "booking_link_generated": true,
    "email_sent": false,
    "lead_status": "IN_PROGRESS"
  }
}
```

## Why This Works (Load-Bearing Insight)

The key idea from the paper + agent systems research:

> You cannot improve what you cannot attribute.

Without traces:

- all failures look like model errors

With traces:

- you separate:
- model failure
- tool failure
- orchestration failure
- external system failure

This turns debugging into a structured decomposition problem instead of guesswork.

## How This Connects to Evaluation (pass@k, CI, judges)

Once traces exist:

### pass@k becomes valid

Because each run is independently attributable.

### Bootstrap confidence intervals become meaningful

Because outcomes are stable per trace group.

### LLM-as-a-judge becomes safer

Because judges evaluate structured artifacts, not raw logs.

Without traces:

> evaluation is statistically invalid

With traces:

> evaluation becomes reproducible inference

## Grounding Commit (What You Should Change in Repo)

1. Add `TraceContext` middleware in FastAPI entrypoints
2. Wrap each service (HubSpot, Cal, Resend) with structured outputs
3. Replace raw returns with typed result objects
4. Add `failure_attribution` resolver module
5. Persist `trace_log.jsonl` per turn
6. Add `step_name + status + error_type` everywhere
7. Modify webhook + outreach pipeline to emit full traces

## What This Ultimately Teaches

The key shift is:

> From “pipeline execution” → “causal system with observable failures”

Your Conversion Engine is already functional.

What is missing is not capability — but **diagnostic structure**.

Once added, every failure becomes:

- explainable
- attributable
- measurable
- improvable

## Closing Insight

The most important upgrade is not better prompts or better models.

It is this:

> Turning agent execution into a traceable causal graph where every failure has a location, a reason, and a responsible component.

That is what enables real evaluation, real debugging, and real improvement.
