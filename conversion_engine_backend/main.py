# conversion_engine_backend/main.py

import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
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
        except Exception:
            body = await request.body()
            data = {"raw": body.decode("utf-8") if body else ""}
    elif "application/x-www-form-urlencoded" in content_type:
        try:
            form = await request.form()
            data = dict(form)
        except Exception:
            data = {"error": "invalid form data"}
    else:
        body = await request.body()
        data = {"raw": body.decode("utf-8") if body else ""}

    # Log to file and console
    logger.info(f"Received webhook: {data}")
    print("Received webhook:", data)

    return JSONResponse({"received": True, "data": data})
