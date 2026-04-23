# conversion_engine_backend/main.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        # Try JSON first
        data = await request.json()
    except Exception:
        # Fallback: read raw body or form data
        form = await request.form()
        data = dict(form)

    print("Received webhook:", data)
    return JSONResponse({"received": True, "data": data})