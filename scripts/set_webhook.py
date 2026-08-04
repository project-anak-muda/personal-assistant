"""Register, inspect, or clear the Telegram webhook.

Telegram allows either long polling or a webhook, never both. Registering a
webhook stops `telegram_bot.py` from receiving anything, and running
`telegram_bot.py` clears the webhook on startup.

Usage:
    uv run python -m scripts.set_webhook set https://<service>.run.app
    uv run python -m scripts.set_webhook info
    uv run python -m scripts.set_webhook delete
"""
import os
import sys
import asyncio
import httpx

from dotenv import load_dotenv

from constants.log import LOGGER
from services.telegram import api_url


async def set_webhook(base_url: str) -> None:
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not secret:
        LOGGER.error(
            "TELEGRAM_WEBHOOK_SECRET is not set. Generate one with:\n"
            "  python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
        sys.exit(1)

    url = f"{base_url.rstrip('/')}/telegram/webhook"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            api_url("setWebhook"),
            json={
                "url": url,
                "secret_token": secret,
                "allowed_updates": ["message", "edited_message"],
                # Drop anything queued while the bot was offline so a redeploy
                # does not replay a backlog of stale messages.
                "drop_pending_updates": True,
            },
        )
        resp.raise_for_status()
        LOGGER.info(f"setWebhook -> {url}: {resp.json()}")

async def delete_webhook() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(api_url("deleteWebhook"), json={"drop_pending_updates": False})
        resp.raise_for_status()
        LOGGER.info(f"deleteWebhook: {resp.json()}")

async def webhook_info() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(api_url("getWebhookInfo"))
        resp.raise_for_status()
        LOGGER.info(f"getWebhookInfo: {resp.json()}")

async def main() -> None:
    load_dotenv()

    command = sys.argv[1] if len(sys.argv) > 1 else "info"

    if command == "set":
        if len(sys.argv) < 3:
            LOGGER.error("Usage: python -m scripts.set_webhook set https://<service>.run.app")
            sys.exit(1)
        await set_webhook(sys.argv[2])
    elif command == "delete":
        await delete_webhook()
    elif command == "info":
        await webhook_info()
    else:
        LOGGER.error(f"Unknown command '{command}'. Use: set | info | delete")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
