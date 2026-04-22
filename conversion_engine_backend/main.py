from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "FastAPI is running on Render"}

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    print("Received webhook:", data)
    return {"received": True}
