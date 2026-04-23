# conversion_engine_backend/main.py

import json
import logging
import os

import resend
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from hubspot import HubSpot
from hubspot.crm.contacts import SimplePublicObjectInput

# --- Observability: Langfuse ---
from langfuse import Langfuse

# --- Load environment variables ---
load_dotenv()

# --- Initialise API Clients ---
resend.api_key = os.environ.get("RESEND_API_KEY")
hubspot_client = HubSpot(access_token=os.environ.get("HUBSPOT_ACCESS_TOKEN"))

# --- Initialise Langfuse ---
langfuse = Langfuse(
    public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
    host="https://cloud.langfuse.com",  # default cloud host
)

# --- Get Email Addresses from Environment ---
TO_EMAIL = os.environ.get("RESEND_EMAIL")
FROM_EMAIL = os.environ.get(
    "RESEND_FROM_EMAIL", "Acme <onboarding@resend.dev>"
)  # Uses a default if not set

app = FastAPI()

# --- Configure Logging ---
logger = logging.getLogger("webhook_logger")
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def send_email_notification(sms_from: str, sms_text: str):
    """
    Uses Resend to send an email notification about a new incoming SMS.
    """
    if not resend.api_key:
        logger.error("RESEND_API_KEY is not set. Cannot send email.")
        return
    if not TO_EMAIL:
        logger.error(
            "RESEND_EMAIL environment variable is not set. Cannot send notification."
        )
        return

    subject = f"New SMS Lead from {sms_from}"
    html_body = f"""
        <h3>New Lead via SMS!</h3>
        <p>You've received a new message through the Conversion Engine:</p>
        <ul>
            <li><strong>From:</strong> {sms_from}</li>
            <li><strong>Message:</strong> {sms_text}</li>
        </ul>
        <p>Please follow up promptly.</p>
    """

    try:
        params = {
            "from": FROM_EMAIL,
            "to": [TO_EMAIL],
            "subject": subject,
            "html": html_body,
        }
        email = resend.Emails.send(params)
        logger.info(f"Email notification sent successfully via Resend to {TO_EMAIL}")

        # --- Langfuse trace for email notification ---
        trace = langfuse.trace(name="email_notification", input=params)
        trace.log(f"Sent email notification to {TO_EMAIL}", level="info")
        trace.end()

    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")


@app.get("/")
def read_root():
    """
    A simple endpoint to confirm the server is running.
    """
    return {"status": "ok", "message": "FastAPI is running on Render"}


@app.get("/create-test-contact")
def create_hubspot_contact():
    """
    Creates a single test contact in HubSpot to verify the API connection.
    Access this endpoint by going to <rendered-url>/create-test-contact in your browser.
    """
    if not hubspot_client.access_token:
        logger.error("HUBSPOT_ACCESS_TOKEN is not set. Cannot create contact.")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "HubSpot API key is not configured.",
            },
        )

    try:
        properties = {
            "email": "test.contact@example.com",
            "firstname": "Test",
            "lastname": "Contact",
            "phone": "+1234567890",
            "lifecyclestage": "lead",
        }
        simple_public_object_input = SimplePublicObjectInput(properties=properties)
        api_response = hubspot_client.crm.contacts.basic_api.create(
            simple_public_object_input_for_create=simple_public_object_input
        )

        logger.info(f"Successfully created HubSpot contact with ID: {api_response.id}")

        # --- Langfuse trace for HubSpot contact creation ---
        trace = langfuse.trace(name="hubspot_contact_creation", input=properties)
        trace.log(f"Created HubSpot contact ID: {api_response.id}", level="info")
        trace.end()

        return JSONResponse(
            content={"status": "success", "contact_id": api_response.id}
        )

    except Exception as e:
        logger.error(f"Failed to create HubSpot contact: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Handles incoming webhooks from Africa's Talking, creates a HubSpot contact,
    sends an email notification, and logs everything to Langfuse.
    """
    content_type = request.headers.get("content-type", "").lower()

    if "application/x-www-form-urlencoded" in content_type:
        try:
            form_data = await request.form()
            data = dict(form_data)
            logger.info(f"Successfully received form data: {data}")

            sms_from = data.get("from")
            sms_text = data.get("text")

            if sms_from and sms_text:
                logger.info(
                    f"Processing SMS from {sms_from} with message: '{sms_text}'"
                )
                send_email_notification(sms_from=sms_from, sms_text=sms_text)

                # --- Langfuse trace for SMS webhook ---
                trace = langfuse.trace(name="sms_webhook", input=data)
                trace.log(f"Received SMS from {sms_from}", level="info")
                trace.end()

            return JSONResponse({"received": True, "data": data})

        except Exception as e:
            logger.error(f"Error parsing form data: {e}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"received": False, "error": "Could not parse form data."},
            )

    elif "application/json" in content_type:
        try:
            body = await request.body()
            if not body:
                logger.info("Empty JSON request (health check).")
                return JSONResponse(
                    {"received": True, "message": "Empty JSON body acknowledged."}
                )

            data = json.loads(body)
            logger.info(f"Received JSON data: {data}")

            # --- Langfuse trace for JSON webhook ---
            trace = langfuse.trace(name="json_webhook", input=data)
            trace.log("Received JSON webhook event", level="info")
            trace.end()

            return JSONResponse({"received": True, "data": data})

        except json.JSONDecodeError:
            body = await request.body()
            logger.error(f"Invalid JSON. Body: {body.decode('utf-8', 'ignore')}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"received": False, "error": "Invalid JSON in request body."},
            )

    else:
        logger.info(
            f"Received a request with unhandled or missing Content-Type: {content_type}"
        )

        # --- Langfuse trace for fallback webhook ---
        trace = langfuse.trace(
            name="fallback_webhook", input={"content_type": content_type}
        )
        trace.log("Unhandled webhook content type", level="warning")
        trace.end()

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "received": True,
                "message": "Request acknowledged but not processed as form data.",
            },
        )
