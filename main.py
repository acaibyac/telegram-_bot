from fastapi import FastAPI, Request, Header, HTTPException
import os

app = FastAPI()

@app.get("/ping")
def ping():
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "Not found")
    return {"message": "Pong!", "telegram_token": tok[:10] + "...hidden"}

@app.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None)
):
    expected = os.environ.get("TELEGRAM_SECRET")  # setat în Render → Environment
    if expected and x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    update = await request.json()  # JSON trimis de Telegram
    # aici vei procesa mesajul primit
    print(update)  # pentru debugging, apare în logs pe Render
    return {"ok": True}