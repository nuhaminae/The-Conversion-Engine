# conversion_engine_backend/main.py

# main.py
import json
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

app = FastAPI()

# --- Configure logging ---
logger = logging.getLogger("webhook_logger")
logger.setLevel(logging.INFO)
# Using a simple StreamHandler to log to the console, which Render captures.
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


@app.get("/")
def read_root():
    """Handles GET requests to the root URL for health checks."""
    return {"status": "ok", "message": "FastAPI is running on Render"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Handles incoming webhooks, determining the correct parsing strategy
    based on the Content-Type header.
    """
    content_type = request.headers.get("content-type", "").lower()

    # Strategy 1: The request is form data (most likely from Africa's Talking)
    if "application/x-www-form-urlencoded" in content_type:
        try:
            data = await request.form()
            data_dict = dict(data)
            logger.info(f"Successfully received form data: {data_dict}")

            # --- Your Business Logic Here ---
            # Example: Accessing SMS details
            sms_from = data_dict.get("from")
            sms_text = data_dict.get("text")
            if sms_from and sms_text:
                logger.info(f"Received SMS from {sms_from} with message: '{sms_text}'")
            # --- End of Business Logic ---

            return JSONResponse({"received": True, "data": data_dict})

        except Exception as e:
            logger.error(f"Error parsing form data: {e}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"received": False, "error": "Could not parse form data."},
            )

    # Strategy 2: The request is JSON
    elif "application/json" in content_type:
        try:
            # Check for empty body before trying to parse
            body = await request.body()
            if not body:
                logger.info("Received empty JSON request (health check).")
                return JSONResponse(
                    {"received": True, "message": "Empty JSON body acknowledged."}
                )

            data = json.loads(body)
            logger.info(f"Successfully received JSON data: {data}")
            return JSONResponse({"received": True, "data": data})

        except json.JSONDecodeError:
            logger.error(
                f"Received invalid JSON. Body: {body.decode('utf-8', 'ignore')}"
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"received": False, "error": "Invalid JSON in request body."},
            )

    # Fallback Strategy: Handle empty pings or unknown content types
    else:
        # This handles the Render health checks which may have no content-type and an empty body
        logger.info(
            f"Received a request with unhandled or missing Content-Type: {content_type}"
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "received": True,
                "message": "Request with no parsable content acknowledged.",
            },
        )
