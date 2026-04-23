# conversion_engine_backend/main.py

from fastapi import FastAPI, Request
import datetime
import json

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "FastAPI is running on Render"}

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    print("Received webhook:", data)
    
    # Append to log file with timestamp
    with open("webhook.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} - {json.dumps(data)}\n")
    
    return {"received": True}
