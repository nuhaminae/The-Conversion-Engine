# conversion_engine_backend/main.py

import json
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request, status
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
    return {"status": "ok", "message": "FastAPI is running on Render"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    content_type = request.headers.get("content-type", "").lower()
    data = {}

    if "application/json" in content_type:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            # Log the error and return a 400 Bad Request response.
            # Do not try to re-read the request body here.
            logger.error("Webhook received a request with invalid JSON.")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"received": False, "error": "Invalid JSON body received."},
            )
    elif "application/x-www-form-urlencoded" in content_type:
        try:
            form = await request.form()
            data = dict(form)
        except Exception:
            # This can happen if the form data is malformed.
            logger.error("Webhook received invalid form data.")
            data = {"error": "invalid form data"}
    else:
        # Handle other content types or lack thereof.
        body = await request.body()
        data = {"raw": body.decode("utf-8") if body else "empty body"}

    # Log to file and console on success
    logger.info(f"Successfully received webhook: {data}")
    print("Successfully received webhook:", data)

    return JSONResponse({"received": True, "data": data})
