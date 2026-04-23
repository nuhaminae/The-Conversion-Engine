# conversion_engine_backend/main.py

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import resend
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

app = FastAPI()

# --- Configure logging ---
logger = logging.getLogger("webhook_logger")
logger.setLevel(logging.INFO)

# Log to console (captured by Render)
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Log to file (rotating)
file_handler = RotatingFileHandler("webhook.log", maxBytes=5*1024*1024, backupCount=3)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# --- Configure Resend ---
# IMPORTANT: replace with environment variable in production
resend.api_key = os.environ.get("RESEND_API_KEY") 
RESEND_EMAIL = os.environ.get("RESEND_EMAIL")

@app.get("/")
def read_root():
    """Handles GET requests to the root URL for health checks."""
    return {"status": "ok", "message": "FastAPI is running on Render"}


@app.get("/send-test-email")
def send_test_email():
    """Send a test email via Resend to verify outbound email works."""
    params = {
        "from": "onboarding@resend.dev",   # Resend sandbox sender
        "to": RESEND_EMAIL,    # Replace with your email
        "subject": "Test Email from FastAPI",
        "html": "<p>Hello from Resend + FastAPI!</p>",
    }
    email = resend.Emails.send(params)
    logger.info(f"Sent test email: {email}")
    return {"status": "sent", "id": email["id"]}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Handles incoming webhooks, determining the correct parsing strategy
    based on the Content-Type header.
    """
    content_type = request.headers.get("content-type", "").lower()

    # Strategy 1: Africa's Talking (form data)
    if "application/x-www-form-urlencoded" in content_type:
        try:
            data = await request.form()
            data_dict = dict(data)
            logger.info(f"Received form data: {data_dict}")

            sms_from = data_dict.get("from")
            sms_text = data_dict.get("text")
            if sms_from and sms_text:
                logger.info(f"SMS from {sms_from}: '{sms_text}'")

            return JSONResponse({"received": True, "data": data_dict})

        except Exception as e:
            logger.error(f"Error parsing form data: {e}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"received": False, "error": "Could not parse form data."},
            )

    # Strategy 2: JSON (Resend, Cal.com, HubSpot, etc.)
    elif "application/json" in content_type:
        try:
            body = await request.body()
            if not body:
                logger.info("Empty JSON request (health check).")
                return JSONResponse({"received": True, "message": "Empty JSON body acknowledged."})

            data = json.loads(body)
            logger.info(f"Received JSON data: {data}")

            # Example: Resend event logging
            event_type = data.get("type")
            if event_type:
                logger.info(f"Resend event type: {event_type}")

            return JSONResponse({"received": True, "data": data})

        except json.JSONDecodeError:
            body = await request.body()
            logger.error(f"Invalid JSON. Body: {body.decode('utf-8', 'ignore')}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"received": False, "error": "Invalid JSON in request body."},
            )

    # Fallback Strategy: Handle empty pings or unknown content types
    else:
        logger.info(f"Unhandled or missing Content-Type: {content_type}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"received": True, "message": "Request acknowledged with no parsable content."},
        )
