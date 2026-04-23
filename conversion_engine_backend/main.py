# conversion_engine_backend/main.py
import json
import logging
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from fastapi import Body, FastAPI, Form, Request, status
from fastapi.responses import JSONResponse

app = FastAPI()

# --- Configure logging to webhook.log ---
logger = logging.getLogger("webhook_logger")
logger.setLevel(logging.INFO)

# Rotating file handler: keeps logs manageable
handler = RotatingFileHandler("webhook.log", maxBytes=5 * 1024 * 1024, backupCount=3)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


@app.get("/")
def read_root():
    """Handles GET requests to the root URL."""
    return {"status": "ok", "message": "FastAPI is running on Render"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    A robust webhook handler that correctly processes different content types.
    It can handle JSON, URL-encoded form data, and empty 'ping' requests.
    """
    data = None
    content_type = request.headers.get("content-type", "").lower()

    # It's important to check for a body before trying to parse it
    body = await request.body()
    if not body:
        logger.info("Webhook received an empty request body (likely a health check).")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"received": True, "message": "Empty body acknowledged."},
        )

    # 1. Handle JSON data
    if "application/json" in content_type:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            logger.error(
                f"Webhook received invalid JSON. Body: {body.decode('utf-8', 'ignore')}"
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"received": False, "error": "Invalid JSON in request body."},
            )

    # 2. Handle Form data (like from Africa's Talking)
    elif "application/x-www-form-urlencoded" in content_type:
        try:
            # Use FastAPI's/Starlette's built-in robust form parser
            form_data = await request.form()
            data = dict(form_data)
        except Exception as e:
            logger.error(
                f"Failed to parse form data. Body: {body.decode('utf-8', 'ignore')}. Error: {e}"
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "received": False,
                    "error": "Malformed form data in request body.",
                },
            )

    # 3. Handle any other case
    else:
        # Treat as raw text if content-type is unknown or not handled
        logger.warning(f"Received webhook with unhandled content-type: {content_type}")
        data = {"raw_body": body.decode("utf-8", "ignore")}

    # Here, data should be a dictionary
    logger.info(f"Successfully received and parsed webhook: {data}")
    print("Successfully received and parsed webhook:", data)

    # For example, to get the 'from' and 'text' from an Africa's Talking SMS:
    if data and "from" in data and "text" in data:
        sms_sender = data.get("from")
        sms_text = data.get("text")
        print(f"Received SMS from {sms_sender} with message: '{sms_text}'")

    return JSONResponse({"received": True, "data": data})
