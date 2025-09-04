import os
from fastapi import FastAPI
from dotenv import load_dotenv

# încarcă variabilele din .env
load_dotenv()

app = FastAPI()

@app.get("/ping")
def ping():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "Not found")
    return {"message": "Pong!", "telegram_token": token[:10] + "...hidden"}