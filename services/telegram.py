import os
import uuid
import httpx

from typing import Optional, Tuple

from constants.log import LOGGER
from utils.gsheet import read_all
from constants.config import WHITELIST_USERS_SHEET
from utils.helpers import build_thread_id, build_user_message, extract_agent_response


def api_url(method: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var is not set")
    return f"https://api.telegram.org/bot{token}/{method}"

def file_url(file_path: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    return f"https://api.telegram.org/file/bot{token}/{file_path}"

async def send_text(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    resp = await client.post(
        api_url("sendMessage"),
        json={"chat_id": chat_id, "text": text[:4096]},
    )
    if resp.status_code >= 400:
        LOGGER.error(f"Telegram send failed: {resp.status_code} {resp.text}")

async def fetch_photo(
    client: httpx.AsyncClient, file_id: str
) -> Tuple[bytes, str]:
    info = await client.get(api_url("getFile"), params={"file_id": file_id})
    info.raise_for_status()
    file_path = info.json()["result"]["file_path"]

    binary = await client.get(file_url(file_path))
    binary.raise_for_status()

    mime = "image/jpeg"
    lowered = file_path.lower()
    if lowered.endswith(".png"):
        mime = "image/png"
    elif lowered.endswith(".webp"):
        mime = "image/webp"
    return binary.content, mime

async def handle_message(client: httpx.AsyncClient, agent, message: dict) -> None:
    """Run one Telegram message through the agent and reply.

    Shared by both transports: the long-polling loop (`telegram_bot.py`) and the
    webhook endpoint (`routers/telegram.py`).
    """
    chat_id = message["chat"]["id"]
    username = message["chat"].get("username")

    whitelist_users = read_all(WHITELIST_USERS_SHEET)
    whitelist_users = list(set([i.get('users') for i in whitelist_users if i.get('users')]))

    if username not in whitelist_users:
        await send_text(client, chat_id, "Maaf, Anda tidak diizinkan menggunakan bot ini.")
        return

    text = ""
    image_bytes: Optional[bytes] = None
    image_mime = "image/jpeg"

    if "photo" in message:
        largest = message["photo"][-1]
        image_bytes, image_mime = await fetch_photo(client, largest["file_id"])
        text = message.get("caption", "") or "Tolong proses gambar ini."
    elif "text" in message:
        text = message["text"]
    else:
        await send_text(
            client,
            chat_id,
            "Maaf, untuk saat ini saya hanya bisa memproses teks atau gambar.",
        )
        return

    user_message = build_user_message(
        query=text, image_bytes=image_bytes, image_mime=image_mime
    )

    thread_id = build_thread_id(chat_id)
    run_id = str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": f"{thread_id}_{run_id}",
        "run_id": run_id,
    }
    response = await agent.ainvoke({"messages": [user_message]}, config=config)
    parsed = extract_agent_response(response, thread_id, run_id)

    reply = (
        parsed.get("data", {}).get("final_answer")
        or "Maaf, saya tidak mendapat respons. Coba lagi ya."
    )
    if not isinstance(reply, str):
        reply = str(reply)

    await send_text(client, chat_id, reply)
