# conversion_engine_backend/main.py
# added after peer's explainer



"""
FastAPI backend for The Conversion Engine.

This version adds step-level causal tracing for the warm-lead reply path.

Why:
    A failed scheduling outcome should not collapse into a generic
    "booking failed" or "agent failed" event.

    The trace now separates:
    - model intent classification
    - HubSpot lookup/update
    - Cal.com booking-link generation
    - LLM reply drafting
    - Resend email delivery
    - fallback policy
    - final business outcome
    - failure attribution

Output:
    Each processed Resend webhook appends a JSONL trace to:

        eval/trace_log.jsonl
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langfuse import get_client, observe
from pydantic import BaseModel, Field

import llm.core as llm_core
import llm.prompts as prompts
from enrichment import core as enrichment_core
from services import cal_service, email_service, hubspot_service

# ---------------------------------------------------------------------
# Windows asyncio compatibility
# ---------------------------------------------------------------------

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

# ---------------------------------------------------------------------
# Logging and Langfuse
# ---------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

langfuse_client = get_client()

# ---------------------------------------------------------------------
# Request / webhook models
# ---------------------------------------------------------------------


class OutreachPayload(BaseModel):
    email: str
    name: str
    company: str
    jobs_page_url: str


class FromEmail(BaseModel):
    email: str


class ResendData(BaseModel):
    # Resend sends this field as "from".
    from_: FromEmail = Field(alias="from")
    text: Optional[str] = None
    html: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class ResendWebhookPayload(BaseModel):
    type: str
    data: ResendData


# ---------------------------------------------------------------------
# Trace schema
# ---------------------------------------------------------------------


class StepStatus(str, Enum):
    success = "success"
    skipped = "skipped"
    not_found = "not_found"
    error = "error"


class FailureStage(str, Enum):
    none = "none"
    model_intent = "model_intent"
    tool_arguments = "tool_arguments"
    tool_runtime = "tool_runtime"
    orchestration = "orchestration"
    external_system = "external_system"
    fallback_missing = "fallback_missing"
    final_delivery = "final_delivery"


class ModelAlternative(BaseModel):
    label: str
    score: Optional[float] = None


class ModelStage(BaseModel):
    intent: str
    confidence: Optional[float] = None
    alternatives: List[ModelAlternative] = Field(default_factory=list)
    prompt_version: str = "reply_classification_v1"
    raw_output: Dict[str, Any] = Field(default_factory=dict)


class ExecutionStep(BaseModel):
    step_name: str
    component: str
    status: StepStatus
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class FailureAttribution(BaseModel):
    failure_stage: FailureStage = FailureStage.none
    component: Optional[str] = None
    step: Optional[str] = None
    reason: Optional[str] = None


class BusinessOutcome(BaseModel):
    booking_link_generated: bool = False
    email_sent: bool = False
    meeting_booked: bool = False
    hubspot_updated: bool = False
    lead_status: Optional[str] = None


class TurnTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    turn_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    prospect_email: Optional[str] = None
    prospect_reply: Optional[str] = None
    our_last_email_body_present: bool = False

    model_stage: Optional[ModelStage] = None
    required_business_action: Optional[str] = None
    execution_steps: List[ExecutionStep] = Field(default_factory=list)

    fallback_policy: Optional[str] = None
    failure_attribution: FailureAttribution = Field(default_factory=FailureAttribution)
    business_outcome: BusinessOutcome = Field(default_factory=BusinessOutcome)

    final_response: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------
# Trace helpers
# ---------------------------------------------------------------------

TRACE_PATH = Path("eval/trace_log.jsonl")


def _model_to_dict(model: BaseModel) -> Dict[str, Any]:
    """Pydantic v1/v2-compatible dump helper."""
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return model.dict()


def write_turn_trace(trace: TurnTrace) -> None:
    """Append one turn trace to eval/trace_log.jsonl."""
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(_model_to_dict(trace), ensure_ascii=False) + "\n")


def add_step(
    trace: TurnTrace,
    *,
    step_name: str,
    component: str,
    status: StepStatus,
    start_time: Optional[float] = None,
    input: Optional[Dict[str, Any]] = None,
    output: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Add a structured execution step to the trace."""
    latency_ms = None
    if start_time is not None:
        latency_ms = int((time.perf_counter() - start_time) * 1000)

    trace.execution_steps.append(
        ExecutionStep(
            step_name=step_name,
            component=component,
            status=status,
            input=input or {},
            output=output or {},
            latency_ms=latency_ms,
            error_type=error_type,
            error_message=error_message,
        )
    )


def find_step(trace: TurnTrace, step_name: str) -> Optional[ExecutionStep]:
    for step in trace.execution_steps:
        if step.step_name == step_name:
            return step
    return None


def resolve_failure(trace: TurnTrace) -> FailureAttribution:
    """
    Resolve the earliest responsible failure stage.

    The resolver prioritizes the business outcome:
    - If the scheduling path succeeded, HubSpot not_found is treated as a
      CRM-state warning, not as the primary failure.
    - If the booking link was generated but the email was not sent, the
      responsible failure is final delivery / Resend.
    """

    if trace.model_stage is None:
        return FailureAttribution(
            failure_stage=FailureStage.model_intent,
            component="llm",
            step="classify_intent",
            reason="No intent classification was recorded.",
        )

    intent = trace.model_stage.intent

    # Scheduling path attribution.
    if intent in {"INTERESTED_BOOK_MEETING", "INTERESTED_QUESTION"}:
        if trace.business_outcome.booking_link_generated and trace.business_outcome.email_sent:
            return FailureAttribution()

        cal_step = find_step(trace, "cal_link_generation")
        if not trace.business_outcome.booking_link_generated:
            if cal_step and cal_step.status == StepStatus.error:
                return FailureAttribution(
                    failure_stage=FailureStage.tool_runtime,
                    component="cal",
                    step="cal_link_generation",
                    reason=cal_step.error_message or "Cal.com link generation failed.",
                )
            return FailureAttribution(
                failure_stage=FailureStage.orchestration,
                component="reply_handler",
                step="cal_link_generation",
                reason="Booking intent was detected, but no booking link was generated.",
            )

        resend_step = find_step(trace, "resend_email")
        if not trace.business_outcome.email_sent:
            return FailureAttribution(
                failure_stage=FailureStage.final_delivery,
                component="resend",
                step="resend_email",
                reason=(
                    resend_step.error_message
                    if resend_step and resend_step.error_message
                    else "Booking link was generated, but the reply email was not sent."
                ),
            )

    # Not-interested path attribution.
    if intent == "NOT_INTERESTED":
        hubspot_step = find_step(trace, "hubspot_update_contact")
        if hubspot_step and hubspot_step.status == StepStatus.error:
            return FailureAttribution(
                failure_stage=FailureStage.tool_runtime,
                component="hubspot",
                step="hubspot_update_contact",
                reason=hubspot_step.error_message or "HubSpot lead-status update failed.",
            )

    # Wrong-person path attribution.
    if intent == "WRONG_PERSON":
        if not trace.business_outcome.email_sent:
            resend_step = find_step(trace, "resend_email")
            if resend_step and resend_step.status == StepStatus.error:
                return FailureAttribution(
                    failure_stage=FailureStage.final_delivery,
                    component="resend",
                    step="resend_email",
                    reason=resend_step.error_message or "Wrong-person reply was not sent.",
                )

    # Generic tool errors only matter if no primary business outcome succeeded.
    for step in trace.execution_steps:
        if step.status == StepStatus.error:
            return FailureAttribution(
                failure_stage=FailureStage.tool_runtime,
                component=step.component,
                step=step.step_name,
                reason=step.error_message or "Tool step returned error.",
            )

    return FailureAttribution()


def classify_required_action(intent: str) -> str:
    if intent in {"INTERESTED_BOOK_MEETING", "INTERESTED_QUESTION"}:
        return "send_booking_link"
    if intent == "NOT_INTERESTED":
        return "mark_unqualified"
    if intent == "WRONG_PERSON":
        return "acknowledge_referral_or_request_contact"
    return "no_action_or_human_review"


# ---------------------------------------------------------------------
# Service wrappers for traceable tool outcomes
# ---------------------------------------------------------------------


def safe_find_contact(email: str) -> Dict[str, Any]:
    try:
        contact_id = hubspot_service.find_contact_by_email(email)
        if contact_id:
            return {
                "status": StepStatus.success,
                "payload": {"contact_id": contact_id},
                "error_type": None,
                "error_message": None,
            }

        return {
            "status": StepStatus.not_found,
            "payload": {"email": email},
            "error_type": "contact_not_found",
            "error_message": "No HubSpot contact found for email.",
        }
    except Exception as exc:
        return {
            "status": StepStatus.error,
            "payload": {"email": email},
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
        }


def safe_get_contact_property(contact_id: str, property_name: str) -> Dict[str, Any]:
    try:
        value = hubspot_service.get_contact_property(contact_id, property_name)
        if value:
            return {
                "status": StepStatus.success,
                "payload": {property_name: value},
                "error_type": None,
                "error_message": None,
            }

        return {
            "status": StepStatus.not_found,
            "payload": {"contact_id": contact_id, property_name: value},
            "error_type": "property_missing",
            "error_message": f"HubSpot property '{property_name}' is missing.",
        }
    except Exception as exc:
        return {
            "status": StepStatus.error,
            "payload": {"contact_id": contact_id, "property": property_name},
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
        }


def safe_update_contact(contact_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    try:
        success = hubspot_service.update_contact_property(contact_id, properties)
        if success:
            return {
                "status": StepStatus.success,
                "payload": {"contact_id": contact_id, "properties": properties},
                "error_type": None,
                "error_message": None,
            }

        return {
            "status": StepStatus.error,
            "payload": {"contact_id": contact_id, "properties": properties},
            "error_type": "hubspot_update_failed",
            "error_message": "HubSpot update returned False.",
        }
    except Exception as exc:
        return {
            "status": StepStatus.error,
            "payload": {"contact_id": contact_id, "properties": properties},
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
        }


def safe_create_contact(
    email: str, first_name: str, last_name: str, company_name: str
) -> Dict[str, Any]:
    try:
        contact_id = hubspot_service.create_contact(email, first_name, last_name, company_name)
        if contact_id:
            return {
                "status": StepStatus.success,
                "payload": {"contact_id": contact_id},
                "error_type": None,
                "error_message": None,
            }

        return {
            "status": StepStatus.error,
            "payload": {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "company": company_name,
            },
            "error_type": "hubspot_create_failed",
            "error_message": "HubSpot create_contact returned no contact_id.",
        }
    except Exception as exc:
        return {
            "status": StepStatus.error,
            "payload": {"email": email, "company": company_name},
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
        }


def safe_get_booking_link(partner_name: str) -> Dict[str, Any]:
    try:
        booking_link = cal_service.get_booking_link(partner_name)
        return {
            "status": StepStatus.success if booking_link else StepStatus.error,
            "payload": {"booking_link": booking_link, "partner_name": partner_name},
            "error_type": None if booking_link else "missing_booking_link",
            "error_message": None if booking_link else "Cal.com returned no booking link.",
        }
    except Exception as exc:
        return {
            "status": StepStatus.error,
            "payload": {"partner_name": partner_name},
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
        }


def safe_send_email(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    try:
        response = email_service.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
        )

        if isinstance(response, dict) and response.get("error"):
            return {
                "status": StepStatus.error,
                "payload": {"to_email": to_email, "subject": subject},
                "error_type": "resend_send_failed",
                "error_message": str(response.get("error")),
            }

        return {
            "status": StepStatus.success,
            "payload": {
                "to_email": to_email,
                "subject": subject,
                "response": response,
            },
            "error_type": None,
            "error_message": None,
        }
    except Exception as exc:
        return {
            "status": StepStatus.error,
            "payload": {"to_email": to_email, "subject": subject},
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
        }


# ---------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------

app = FastAPI(
    title="The Conversion Engine",
    description="Automated lead generation and conversion system for Tenacious Consulting.",
)


@app.get("/", tags=["Health Check"])
@observe()
def read_root():
    return {"status": "ok", "message": "Conversion Engine is running."}


# ---------------------------------------------------------------------
# Outreach Pipeline
# ---------------------------------------------------------------------


@app.post("/start-outreach", tags=["Core Pipeline"])
@observe()
async def start_outreach_pipeline(payload: OutreachPayload):
    prospect_email = payload.email
    prospect_name = payload.name
    company_name = payload.company
    jobs_page_url = payload.jobs_page_url

    langfuse_client.update_current_span(
        name="full-outreach-pipeline",
        metadata={"company": company_name},
    )

    logging.info("Starting outreach pipeline for %s at %s", prospect_name, company_name)

    # 1. CRM find/create.
    contact_id = hubspot_service.find_contact_by_email(prospect_email)

    if not contact_id:
        first_name = prospect_name.split(" ")[0]
        last_name = (
            " ".join(prospect_name.split(" ")[1:])
            if " " in prospect_name
            else ""
        )

        contact_id = hubspot_service.create_contact(
            prospect_email,
            first_name,
            last_name,
            company_name,
        )

        if not contact_id:
            logging.error("Failed to find or create HubSpot contact. Aborting outreach.")
            raise HTTPException(
                status_code=500,
                detail="Failed to create HubSpot contact.",
            )

    hubspot_service.update_contact_property(contact_id, {"hs_lead_status": "OPEN"})

    # 2. Enrichment.
    hiring_brief = await enrichment_core.enrich_prospect(company_name, jobs_page_url)

    # 3. LLM draft.
    prompt = prompts.INITIAL_OUTREACH_PROMPT.format(
        prospect_name=prospect_name,
        prospect_company=company_name,
        hiring_signal_brief=hiring_brief,
    )

    email_content = await llm_core.generate_llm_response(prompt, prompts.SYSTEM_PERSONA)

    if "error" in email_content or not all(
        [email_content.get("subject"), email_content.get("body")]
    ):
        logging.error(
            "Failed to generate email content for %s. Error: %s",
            prospect_email,
            email_content.get("error"),
        )
        raise HTTPException(
            status_code=500,
            detail="LLM failed to generate email content.",
        )

    # 4. Send email.
    send_result = email_service.send_email(
        to_email=prospect_email,
        subject=email_content["subject"],
        body=email_content["body"],
    )

    if isinstance(send_result, dict) and send_result.get("error"):
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send outreach email: {send_result.get('error')}",
        )

    # 5. CRM note.
    hubspot_service.update_contact_property(
        contact_id,
        {"last_outreach_note": "Initial outreach sent."},
    )

    return {
        "status": "success",
        "message": f"Outreach process started for {prospect_email}.",
    }


# ---------------------------------------------------------------------
# Resend Webhook
# ---------------------------------------------------------------------


@app.post("/webhook/resend", tags=["Webhook Handlers"])
@observe()
async def handle_resend_webhook(payload: ResendWebhookPayload):
    """
    Handle inbound reply webhooks from Resend.

    The trace produced here is the main grounding artifact for the
    agent/tool-use-internals question.
    """

    if payload.type != "email.created":
        return {"status": "ignored", "reason": f"Event type is {payload.type}"}

    prospect_email = payload.data.from_.email
    prospect_reply_body = payload.data.text or ""
    our_last_email_body = payload.data.html or ""

    trace = TurnTrace(
        prospect_email=prospect_email,
        prospect_reply=prospect_reply_body,
        our_last_email_body_present=bool(our_last_email_body),
    )

    if not prospect_email or not prospect_reply_body:
        trace.failure_attribution = FailureAttribution(
            failure_stage=FailureStage.orchestration,
            component="resend_webhook",
            step="parse_webhook_payload",
            reason="Missing sender email or reply body from webhook payload.",
        )
        write_turn_trace(trace)
        return {
            "status": "error",
            "trace_id": trace.trace_id,
            "reason": "Missing sender or body from webhook payload.",
        }

    logging.info("Received reply from %s", prospect_email)
    langfuse_client.update_current_span(
        name="handle-email-reply",
        metadata={"trace_id": trace.trace_id, "prospect_email": prospect_email},
    )

    # -----------------------------------------------------------------
    # 1. Classify reply intent.
    # -----------------------------------------------------------------

    classification_prompt = prompts.REPLY_CLASSIFICATION_PROMPT.format(
        our_last_email_body=our_last_email_body,
        prospect_reply_body=prospect_reply_body,
    )

    start = time.perf_counter()

    try:
        classification_result = await llm_core.generate_llm_response(
            classification_prompt,
            prompts.SYSTEM_PERSONA,
        )

        if not isinstance(classification_result, dict):
            classification_result = {
                "intent": "UNSURE",
                "confidence": None,
                "alternatives": [],
                "raw": str(classification_result),
            }

        intent = str(classification_result.get("intent", "UNSURE"))
        confidence = classification_result.get("confidence")
        alternatives_raw = classification_result.get("alternatives", [])

        alternatives: List[ModelAlternative] = []
        if isinstance(alternatives_raw, list):
            for item in alternatives_raw:
                if isinstance(item, dict):
                    label = item.get("intent") or item.get("label")
                    if label:
                        alternatives.append(
                            ModelAlternative(label=str(label), score=item.get("score"))
                        )

        trace.model_stage = ModelStage(
            intent=intent,
            confidence=confidence if isinstance(confidence, (int, float)) else None,
            alternatives=alternatives,
            prompt_version="reply_classification_v2",
            raw_output=classification_result,
        )
        trace.required_business_action = classify_required_action(intent)

        add_step(
            trace,
            step_name="classify_intent",
            component="llm",
            status=StepStatus.success,
            start_time=start,
            input={
                "prompt_version": "reply_classification_v2",
                "reply_present": bool(prospect_reply_body),
                "last_email_present": bool(our_last_email_body),
            },
            output={
                "intent": intent,
                "confidence": trace.model_stage.confidence,
                "alternatives": [_model_to_dict(alt) for alt in alternatives],
            },
        )

        logging.info("Classified intent for %s as: %s", prospect_email, intent)

    except Exception as exc:
        trace.model_stage = ModelStage(
            intent="UNSURE",
            confidence=None,
            alternatives=[],
            prompt_version="reply_classification_v2",
            raw_output={"error": str(exc)},
        )
        trace.required_business_action = "no_action_or_human_review"

        add_step(
            trace,
            step_name="classify_intent",
            component="llm",
            status=StepStatus.error,
            start_time=start,
            input={"prompt_version": "reply_classification_v2"},
            output={},
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )

        trace.failure_attribution = resolve_failure(trace)
        write_turn_trace(trace)

        return {
            "status": "error",
            "trace_id": trace.trace_id,
            "reason": "Intent classification failed.",
            "failure_attribution": _model_to_dict(trace.failure_attribution),
        }

    # -----------------------------------------------------------------
    # 2. HubSpot lookup.
    # -----------------------------------------------------------------

    start = time.perf_counter()
    contact_result = safe_find_contact(prospect_email)

    add_step(
        trace,
        step_name="hubspot_lookup",
        component="hubspot",
        status=contact_result["status"],
        start_time=start,
        input={"email": prospect_email},
        output=contact_result["payload"],
        error_type=contact_result["error_type"],
        error_message=contact_result["error_message"],
    )

    contact_id = contact_result["payload"].get("contact_id")
    prospect_company = "your company"

    # If HubSpot contact is missing, do not drop a warm lead.
    # Continue the booking path when the intent requires it, but record
    # that CRM update could not be completed.
    if contact_id:
        start = time.perf_counter()
        company_result = safe_get_contact_property(contact_id, "company")

        add_step(
            trace,
            step_name="hubspot_get_company",
            component="hubspot",
            status=company_result["status"],
            start_time=start,
            input={"contact_id": contact_id, "property": "company"},
            output=company_result["payload"],
            error_type=company_result["error_type"],
            error_message=company_result["error_message"],
        )

        prospect_company = company_result["payload"].get("company") or "your company"

    else:
        trace.fallback_policy = (
            "hubspot_contact_not_found_continue_booking_path_if_interested"
        )

    # -----------------------------------------------------------------
    # 3. Action branch by intent.
    # -----------------------------------------------------------------

    intent = trace.model_stage.intent if trace.model_stage else "UNSURE"

    if intent in {"INTERESTED_BOOK_MEETING", "INTERESTED_QUESTION"}:
        # 3a. HubSpot status update if possible.
        if contact_id:
            start = time.perf_counter()
            update_result = safe_update_contact(
                contact_id,
                {"hs_lead_status": "IN_PROGRESS"},
            )

            add_step(
                trace,
                step_name="hubspot_update_contact",
                component="hubspot",
                status=update_result["status"],
                start_time=start,
                input={
                    "contact_id": contact_id,
                    "properties": {"hs_lead_status": "IN_PROGRESS"},
                },
                output=update_result["payload"],
                error_type=update_result["error_type"],
                error_message=update_result["error_message"],
            )

            trace.business_outcome.hubspot_updated = (
                update_result["status"] == StepStatus.success
            )
            if trace.business_outcome.hubspot_updated:
                trace.business_outcome.lead_status = "IN_PROGRESS"

        else:
            add_step(
                trace,
                step_name="hubspot_update_contact",
                component="hubspot",
                status=StepStatus.skipped,
                input={"reason": "contact_id_missing"},
                output={},
                error_type="contact_id_missing",
                error_message="Skipped HubSpot update because contact lookup returned not_found.",
            )

        # 3b. Generate booking link.
        start = time.perf_counter()
        cal_result = safe_get_booking_link("nuhamin")

        add_step(
            trace,
            step_name="cal_link_generation",
            component="cal",
            status=cal_result["status"],
            start_time=start,
            input={"partner_name": "nuhamin"},
            output=cal_result["payload"],
            error_type=cal_result["error_type"],
            error_message=cal_result["error_message"],
        )

        booking_link = cal_result["payload"].get("booking_link")
        trace.business_outcome.booking_link_generated = bool(booking_link)

        if not booking_link:
            trace.failure_attribution = resolve_failure(trace)
            write_turn_trace(trace)
            return {
                "status": "error",
                "trace_id": trace.trace_id,
                "intent": intent,
                "reason": "Booking link generation failed.",
                "business_outcome": _model_to_dict(trace.business_outcome),
                "failure_attribution": _model_to_dict(trace.failure_attribution),
            }

        # 3c. Draft reply.
        reply_prompt = prompts.REPLY_DRAFTING_PROMPT.format(
            intent=intent,
            our_last_email_body=our_last_email_body,
            prospect_reply_body=prospect_reply_body,
            cal_link=booking_link,
            prospect_company=prospect_company,
        )

        start = time.perf_counter()

        try:
            reply_content = await llm_core.generate_llm_response(
                reply_prompt,
                prompts.SYSTEM_PERSONA,
            )

            if not isinstance(reply_content, dict):
                reply_content = {
                    "subject": "Re: Tenacious",
                    "body": str(reply_content),
                }

            reply_error = reply_content.get("error")
            subject = reply_content.get("subject") or "Re: Tenacious"
            body = reply_content.get("body") or ""

            draft_status = (
                StepStatus.error if reply_error or not body else StepStatus.success
            )

            add_step(
                trace,
                step_name="reply_drafting",
                component="llm",
                status=draft_status,
                start_time=start,
                input={"intent": intent, "booking_link_present": bool(booking_link)},
                output={
                    "subject_present": bool(subject),
                    "body_present": bool(body),
                },
                error_type="llm_reply_generation_failed" if draft_status == StepStatus.error else None,
                error_message=str(reply_error) if reply_error else None,
            )

            if draft_status == StepStatus.error:
                trace.failure_attribution = resolve_failure(trace)
                write_turn_trace(trace)
                return {
                    "status": "error",
                    "trace_id": trace.trace_id,
                    "intent": intent,
                    "reason": "Reply drafting failed.",
                    "failure_attribution": _model_to_dict(trace.failure_attribution),
                }

        except Exception as exc:
            add_step(
                trace,
                step_name="reply_drafting",
                component="llm",
                status=StepStatus.error,
                start_time=start,
                input={"intent": intent},
                output={},
                error_type=exc.__class__.__name__,
                error_message=str(exc),
            )

            trace.failure_attribution = resolve_failure(trace)
            write_turn_trace(trace)

            return {
                "status": "error",
                "trace_id": trace.trace_id,
                "intent": intent,
                "reason": "Reply drafting failed.",
                "failure_attribution": _model_to_dict(trace.failure_attribution),
            }

        # 3d. Send reply.
        start = time.perf_counter()
        send_result = safe_send_email(prospect_email, subject, body)

        add_step(
            trace,
            step_name="resend_email",
            component="resend",
            status=send_result["status"],
            start_time=start,
            input={"to_email": prospect_email, "subject": subject},
            output=send_result["payload"],
            error_type=send_result["error_type"],
            error_message=send_result["error_message"],
        )

        trace.business_outcome.email_sent = send_result["status"] == StepStatus.success
        trace.final_response = {
            "subject": subject,
            "body_present": bool(body),
            "booking_link_present": booking_link in body,
        }

    elif intent == "NOT_INTERESTED":
        if contact_id:
            start = time.perf_counter()
            update_result = safe_update_contact(
                contact_id,
                {"hs_lead_status": "UNQUALIFIED"},
            )

            add_step(
                trace,
                step_name="hubspot_update_contact",
                component="hubspot",
                status=update_result["status"],
                start_time=start,
                input={
                    "contact_id": contact_id,
                    "properties": {"hs_lead_status": "UNQUALIFIED"},
                },
                output=update_result["payload"],
                error_type=update_result["error_type"],
                error_message=update_result["error_message"],
            )

            trace.business_outcome.hubspot_updated = (
                update_result["status"] == StepStatus.success
            )
            if trace.business_outcome.hubspot_updated:
                trace.business_outcome.lead_status = "UNQUALIFIED"

        else:
            add_step(
                trace,
                step_name="hubspot_update_contact",
                component="hubspot",
                status=StepStatus.skipped,
                input={"reason": "contact_id_missing"},
                output={},
                error_type="contact_id_missing",
                error_message="Skipped UNQUALIFIED update because contact lookup returned not_found.",
            )

        # No reply is sent here to avoid re-engaging someone who declined.
        trace.final_response = {
            "subject": None,
            "body_present": False,
            "note": "No email sent for NOT_INTERESTED intent.",
        }

    elif intent == "WRONG_PERSON":
        # Draft a polite acknowledgement. The existing reply prompt supports this intent.
        reply_prompt = prompts.REPLY_DRAFTING_PROMPT.format(
            intent=intent,
            our_last_email_body=our_last_email_body,
            prospect_reply_body=prospect_reply_body,
            cal_link="not applicable",
            prospect_company=prospect_company,
        )

        start = time.perf_counter()
        reply_content = await llm_core.generate_llm_response(
            reply_prompt,
            prompts.SYSTEM_PERSONA,
        )

        if not isinstance(reply_content, dict):
            reply_content = {
                "subject": "Re: Tenacious",
                "body": str(reply_content),
            }

        subject = reply_content.get("subject") or "Re: Tenacious"
        body = reply_content.get("body") or ""

        add_step(
            trace,
            step_name="reply_drafting",
            component="llm",
            status=StepStatus.success if body else StepStatus.error,
            start_time=start,
            input={"intent": intent},
            output={"subject_present": bool(subject), "body_present": bool(body)},
            error_type=None if body else "llm_reply_generation_failed",
            error_message=None if body else "Reply body missing.",
        )

        if body:
            start = time.perf_counter()
            send_result = safe_send_email(prospect_email, subject, body)

            add_step(
                trace,
                step_name="resend_email",
                component="resend",
                status=send_result["status"],
                start_time=start,
                input={"to_email": prospect_email, "subject": subject},
                output=send_result["payload"],
                error_type=send_result["error_type"],
                error_message=send_result["error_message"],
            )

            trace.business_outcome.email_sent = send_result["status"] == StepStatus.success
            trace.final_response = {"subject": subject, "body_present": True}

    else:
        # UNSURE / Out of Office / no clear action.
        add_step(
            trace,
            step_name="no_action_or_human_review",
            component="orchestrator",
            status=StepStatus.success,
            input={"intent": intent},
            output={"action": "no automated reply sent"},
        )
        trace.final_response = {
            "subject": None,
            "body_present": False,
            "note": "No automated reply sent for unclear intent.",
        }

    # -----------------------------------------------------------------
    # 4. Resolve failure attribution and persist trace.
    # -----------------------------------------------------------------

    trace.failure_attribution = resolve_failure(trace)
    write_turn_trace(trace)

    return {
        "status": "processed",
        "intent": intent,
        "trace_id": trace.trace_id,
        "business_outcome": _model_to_dict(trace.business_outcome),
        "failure_attribution": _model_to_dict(trace.failure_attribution),
    }
    