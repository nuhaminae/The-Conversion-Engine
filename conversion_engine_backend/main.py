# conversion_engine_backend/main.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


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

    print("Received webhook:", data)
    return JSONResponse({"received": True, "data": data})
