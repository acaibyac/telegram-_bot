import os
import time
from collections import deque, defaultdict
from typing import Dict, Any, Optional
import httpx
from fastapi import FastAPI, Request, Header, HTTPException

app = FastAPI()

# ENV
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL   = os.environ.get("OPENAI_MODEL", "gpt-5")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_SECRET = os.environ.get("TELEGRAM_SECRET")

# Memorie scurtă
MAX_TURNS = 6
TTL_SECONDS = 30 * 60
conversations: Dict[int, Dict[str, Any]] = defaultdict(
    lambda: {"messages": deque(maxlen=2 * MAX_TURNS), "last": 0.0}
)

def reset_if_expired(chat_id: int) -> None:
    now = time.time()
    if now - conversations[chat_id]["last"] > TTL_SECONDS:
        conversations[chat_id] = {"messages": deque(maxlen=2 * MAX_TURNS), "last": now}

def add_to_memory(chat_id: int, role: str, content: str) -> None:
    conversations[chat_id]["messages"].append({"role": role, "content": content})
    conversations[chat_id]["last"] = time.time()

# Helpers
async def chat_with_openai(history: list[dict], user_text: str) -> str:
    if not OPENAI_API_KEY:
        return "Lipsește OPENAI_API_KEY în Environment."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "Ești un asistent util. Răspunde scurt, clar și prietenos."},
            *history,
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.6,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        print("OpenAI status:", r.status_code, r.text[:300])
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

async def send_telegram_text(chat_id: int, text: str) -> None:
    if not TELEGRAM_TOKEN:
        print("WARN: TELEGRAM_BOT_TOKEN lipsește din Environment.")
        return
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(send_url, json={"chat_id": chat_id, "text": text})
        print("sendMessage status:", resp.status_code, resp.text)

# Rute
@app.get("/ping")
def ping():
    return {"message": "Pong!", "model": OPENAI_MODEL}

@app.get("/health")
def health():
    return {
        "openai": bool(OPENAI_API_KEY),
        "telegram": bool(TELEGRAM_TOKEN),
        "secret": bool(TELEGRAM_SECRET),
        "model": OPENAI_MODEL,
    }

@app.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    if TELEGRAM_SECRET and x_telegram_bot_api_secret_token != TELEGRAM_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    update = await request.json()
    print(update)

    msg = update.get("message") or {}
    text = (msg.get("text") or "").strip()
    chat_id = msg.get("chat", {}).get("id")
    if not chat_id:
        return {"ok": True}

    low = text.lower()
    if low in ("/start", "start"):
        await send_telegram_text(chat_id, "Salut! Întreabă-mă orice. Comenzi: /ping, /reset")
        return {"ok": True}
    if low == "/ping":
        await send_telegram_text(chat_id, "🏓 Pong!")
        return {"ok": True}
    if low == "/reset":
        conversations.pop(chat_id, None)
        await send_telegram_text(chat_id, "Memoria conversației a fost ștearsă. 📭")
        return {"ok": True}

    if text:
        reset_if_expired(chat_id)
        history = list(conversations[chat_id]["messages"])
        try:
            reply = await chat_with_openai(history, text)
        except Exception as e:
            reply = f"Eroare la OpenAI: {type(e).__name__}"
        add_to_memory(chat_id, "user", text)
        add_to_memory(chat_id, "assistant", reply)
        await send_telegram_text(chat_id, reply)

    return {"ok": True}
