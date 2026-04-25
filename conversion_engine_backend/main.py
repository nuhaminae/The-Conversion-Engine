# conversion_engine_backend/main.py

import json

# Setup & Configuration ---
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv()


from typing import Optional

from pydantic import BaseModel


class FromEmail(BaseModel):
    email: str


class ResendData(BaseModel):
    from_: FromEmail  # use `from_` because `from` is a reserved word
    text: Optional[str]
    html: Optional[str]


class ResendWebhookPayload(BaseModel):
    type: str
    data: ResendData


import logging
import os

from fastapi import FastAPI, HTTPException, Request

# --- Langfuse Integration ---
from langfuse import get_client, observe
from pydantic import BaseModel

import llm.core as llm_core
import llm.prompts as prompts

# --- Custom Modules ---
from enrichment import core as enrichment_core
from services import cal_service, email_service, hubspot_service

# --- Logging & Langfuse ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
langfuse_client = get_client()


# --- Pydantic Model ---
class OutreachPayload(BaseModel):
    email: str
    name: str
    company: str
    jobs_page_url: str


app = FastAPI(
    title="The Conversion Engine",
    description="Automated lead generation and conversion system for Tenacious Consulting.",
)


# --- Health Check ---
@app.get("/", tags=["Health Check"])
@observe()
def read_root():
    return {"status": "ok", "message": "Conversion Engine is running."}


# --- Outreach Pipeline ---
@app.post("/start-outreach", tags=["Core Pipeline"])
@observe()
async def start_outreach_pipeline(payload: OutreachPayload):
    prospect_email = payload.email
    prospect_name = payload.name
    company_name = payload.company
    jobs_page_url = payload.jobs_page_url

    langfuse_client.update_current_span(
        name="full-outreach-pipeline", metadata={"company": company_name}
    )

    logging.info(f"Starting outreach pipeline for {prospect_name} at {company_name}")

    # 1. CRM update
    contact_id = hubspot_service.find_contact_by_email(prospect_email)
    if not contact_id:
        first_name = prospect_name.split(" ")[0]
        last_name = (
            " ".join(prospect_name.split(" ")[1:]) if " " in prospect_name else ""
        )
        contact_id = hubspot_service.create_contact(
            prospect_email, first_name, last_name, company_name
        )

    if not contact_id:
        logging.error("Failed to find or create HubSpot contact. Aborting outreach.")
        raise HTTPException(status_code=500, detail="Failed to create HubSpot contact.")

    hubspot_service.update_contact_property(contact_id, {"hs_lead_status": "OPEN"})

    # 2. Enrichment
    hiring_brief = await enrichment_core.enrich_prospect(company_name, jobs_page_url)

    # 3. LLM Draft
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
            f"Failed to generate email content for {prospect_email}. Error: {email_content.get('error')}"
        )
        raise HTTPException(
            status_code=500, detail="LLM failed to generate email content."
        )

    # 4. Send Email
    email_service.send_email(
        to_email=prospect_email,
        subject=email_content["subject"],
        body=email_content["body"],
    )

    # 5. CRM note (use a safe custom property instead of read-only)
    hubspot_service.update_contact_property(
        contact_id, {"last_outreach_note": "Initial outreach sent."}
    )

    return {
        "status": "success",
        "message": f"Outreach process started for {prospect_email}.",
    }


# --- Resend Webhook ---
@app.post("/webhook/resend", tags=["Webhook Handlers"])
@observe()
async def handle_resend_webhook(payload: ResendWebhookPayload):
    # Only process email.created events
    if payload.type != "email.created":
        return {"status": "ignored", "reason": f"Event type is {payload.type}"}

    prospect_email = payload.data.from_.email
    prospect_reply_body = payload.data.text
    our_last_email_body = payload.data.html

    if not prospect_email or not prospect_reply_body:
        return {"status": "error", "reason": "Missing sender or body from webhook payload."}

    logging.info(f"Received reply from {prospect_email}")
    langfuse_client.update_current_span(name="handle-email-reply")

    # 1. Classify Intent
    classification_prompt = prompts.REPLY_CLASSIFICATION_PROMPT.format(
        our_last_email_body=our_last_email_body,
        prospect_reply_body=prospect_reply_body
    )
    classification_result = await llm_core.generate_llm_response(
        classification_prompt, prompts.SYSTEM_PERSONA
    )
    intent = classification_result.get("intent", "UNSURE")
    logging.info(f"Classified intent for {prospect_email} as: {intent}")

    # 2. Take Action
    contact_id = hubspot_service.find_contact_by_email(prospect_email)
    if not contact_id:
        logging.warning(f"Reply from {prospect_email}, not a known contact.")
        return {"status": "error", "reason": "Contact not found in HubSpot."}

    # Retrieve company name from HubSpot for use in drafting prompt
    prospect_company = hubspot_service.get_contact_property(contact_id, "company") or "your company"


    if intent in ["INTERESTED_BOOK_MEETING", "INTERESTED_QUESTION"]:
        hubspot_service.update_contact_property(contact_id, {"hs_lead_status": "IN_PROGRESS"})
        booking_link = cal_service.get_booking_link("nuhamin")
        reply_prompt = prompts.REPLY_DRAFTING_PROMPT.format(
            intent=intent,
            our_last_email_body=our_last_email_body,
            prospect_reply_body=prospect_reply_body,
            cal_link=booking_link,
            prospect_company=prospect_company
        )
        reply_content = await llm_core.generate_llm_response(
            reply_prompt, prompts.SYSTEM_PERSONA
        )
        email_service.send_email(
            prospect_email, reply_content["subject"], reply_content["body"]
        )

    elif intent == "NOT_INTERESTED":
        hubspot_service.update_contact_property(contact_id, {"hs_lead_status": "UNQUALIFIED"})

    return {"status": "processed", "intent": intent}
