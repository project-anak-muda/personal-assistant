import os
import uuid
import httpx
import asyncio

from typing import Optional, Tuple

from constants.log import LOGGER
from utils.gsheet import read_all
from services.agent_manager import make_graph_single
from constants.config import POLL_TIMEOUT, WHITELIST_USERS_SHEET
from utils.helpers import build_user_message, extract_agent_response


def _api_url(method: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var is not set")
    return f"https://api.telegram.org/bot{token}/{method}"

def _file_url(file_path: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    return f"https://api.telegram.org/file/bot{token}/{file_path}"

async def send_text(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    resp = await client.post(
        _api_url("sendMessage"),
        json={"chat_id": chat_id, "text": text[:4096]},
    )
    if resp.status_code >= 400:
        LOGGER.error(f"Telegram send failed: {resp.status_code} {resp.text}")

async def fetch_photo(
    client: httpx.AsyncClient, file_id: str
) -> Tuple[bytes, str]:
    info = await client.get(_api_url("getFile"), params={"file_id": file_id})
    info.raise_for_status()
    file_path = info.json()["result"]["file_path"]

    binary = await client.get(_file_url(file_path))
    binary.raise_for_status()

    mime = "image/jpeg"
    lowered = file_path.lower()
    if lowered.endswith(".png"):
        mime = "image/png"
    elif lowered.endswith(".webp"):
        mime = "image/webp"
    return binary.content, mime

async def handle_message(client: httpx.AsyncClient, agent, message: dict) -> None:
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

    run_id = str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": f"tg-{chat_id}"},
        "run_name": f"tg-{chat_id}_{run_id}",
        "run_id": run_id,
    }
    response = await agent.ainvoke({"messages": [user_message]}, config=config)
    parsed = extract_agent_response(response, f"tg-{chat_id}", run_id)

    reply = (
        parsed.get("data", {}).get("final_answer")
        or "Maaf, saya tidak mendapat respons. Coba lagi ya."
    )
    if not isinstance(reply, str):
        reply = str(reply)

    await send_text(client, chat_id, reply)

async def run() -> None:
    LOGGER.info("Building agent...")
    agent = await make_graph_single()
    LOGGER.info("Agent ready. Starting Telegram long polling...")

    offset: Optional[int] = None
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT + 10) as client:
        # Ensure no webhook is set (long polling and webhook are mutually exclusive)
        try:
            await client.post(
                _api_url("deleteWebhook"), json={"drop_pending_updates": False}
            )
        except Exception as e:
            LOGGER.warning(f"deleteWebhook failed (ok if no webhook): {e}")

        while True:
            try:
                params = {
                    "timeout": POLL_TIMEOUT,
                    "allowed_updates": ["message", "edited_message"],
                }
                if offset is not None:
                    params["offset"] = offset

                resp = await client.get(_api_url("getUpdates"), params=params)
                resp.raise_for_status()
                data = resp.json()

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message") or update.get("edited_message")
                    if not message:
                        continue
                    try:
                        await handle_message(client, agent, message)
                    except Exception as inner:
                        LOGGER.error(f"Handler error: {inner}", exc_info=True)
                        try:
                            await send_text(
                                client,
                                message["chat"]["id"],
                                f"Internal error: {inner}",
                            )
                        except Exception:
                            pass

            except httpx.ReadTimeout:
                # Normal — long poll closed without new updates. Reconnect.
                continue
            except Exception as e:
                LOGGER.error(f"Polling error: {e}", exc_info=True)
                await asyncio.sleep(3)

if __name__ == "__main__":
    bank_info = read_all('BankInfo')
    bank_info = [f"{i.get('Bank')}\na.n {i.get('Atas Nama')}\n{i.get('Nomor Rekening')}" 
                 for i in bank_info if i.get('Bank') and i.get('Atas Nama') and i.get('Nomor Rekening')]
    bank_info = "\n\n".join(bank_info)
    print(bank_info)
    # try:
    #     asyncio.run(run())
    # except KeyboardInterrupt:
    #     LOGGER.info("Bot stopped.")