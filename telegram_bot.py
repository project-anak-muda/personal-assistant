"""Long-polling transport for the Telegram bot.

Use this for local development and always-on hosts (VPS, docker compose). The
serverless deployment uses the webhook transport in `webhook_app.py` instead —
Telegram allows only one of the two at a time, so this entrypoint clears any
registered webhook on startup.
"""
import json
import httpx
import asyncio

from typing import Optional

from constants.log import LOGGER
from constants.config import POLL_TIMEOUT
from services.agent_manager import make_graph_single
from services.checkpointer import checkpointer_scope
from services.telegram import api_url, handle_message, send_text


async def _poll_loop(agent) -> None:
    offset: Optional[int] = None
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT + 10) as client:
        # Ensure no webhook is set (long polling and webhook are mutually exclusive)
        try:
            await client.post(
                api_url("deleteWebhook"), json={"drop_pending_updates": False}
            )
        except Exception as e:
            LOGGER.warning(f"deleteWebhook failed (ok if no webhook): {e}")

        while True:
            try:
                params = {
                    "timeout": POLL_TIMEOUT,
                    # Telegram expects a JSON-encoded array string here, not
                    # repeated query params (which is what httpx emits for a list).
                    "allowed_updates": json.dumps(["message", "edited_message"]),
                }
                if offset is not None:
                    params["offset"] = offset

                resp = await client.get(api_url("getUpdates"), params=params)
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

async def run() -> None:
    LOGGER.info("Building agent...")
    # The pool must stay open for the whole polling loop, not just graph
    # construction — every ainvoke reads and writes checkpoints through it.
    async with checkpointer_scope() as checkpointer:
        agent = await make_graph_single(checkpointer)
        LOGGER.info("Agent ready. Starting Telegram long polling...")
        await _poll_loop(agent)

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        LOGGER.info("Bot stopped.")
