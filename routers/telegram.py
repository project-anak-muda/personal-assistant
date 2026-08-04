import os
import secrets

from typing import Any, Dict, Optional
from fastapi import APIRouter, Header, HTTPException, Request, status

from constants.log import LOGGER
from services.dedup import claim_update
from services.telegram import handle_message, send_text


telegram_router = APIRouter(
    tags=["TELEGRAM WEBHOOK"],
    prefix="/telegram",
)


def _verify_secret(received: Optional[str]) -> None:
    """Reject anything that did not come from Telegram.

    The Cloud Run URL is public and unauthenticated, so without this check
    anyone who discovers it could drive the agent and burn the LLM quota.
    Telegram echoes the token we registered via setWebhook on every delivery.
    """
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET")

    if not expected:
        LOGGER.error("TELEGRAM_WEBHOOK_SECRET is not set — refusing all webhook calls")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    if not secrets.compare_digest(received or "", expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@telegram_router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _verify_secret(x_telegram_bot_api_secret_token)

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True, "skipped": "no message"}

    update_id = update.get("update_id")
    pool = request.app.context.get("pool")
    if update_id is not None and not await claim_update(pool, update_id):
        LOGGER.info(f"Update {update_id} already processed — ignoring retry")
        return {"ok": True, "skipped": "duplicate"}

    agent = request.app.context["single_agent"]
    client = request.app.context["http"]

    try:
        await handle_message(client, agent, message)
    except Exception as e:
        LOGGER.error(f"Handler error: {e}", exc_info=True)
        try:
            await send_text(client, message["chat"]["id"], f"Internal error: {e}")
        except Exception:
            pass

    # Always 200, even on failure: the update is already claimed, so a non-2xx
    # would only make Telegram redeliver something we will never process.
    return {"ok": True}
