# conversion_engine_backend/main.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "FastAPI is running on Render"}

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = None
    try:
        # Try JSON first
        data = await request.json()
    except Exception:
        try:
            # Fallback: form data
            form = await request.form()
            data = dict(form)
        except Exception:
            # Fallback: raw body (may be empty)
            body = await request.body()
            data = {"raw": body.decode("utf-8") if body else ""}

    print("Received webhook:", data)
    return JSONResponse({"received": True, "data": data})
