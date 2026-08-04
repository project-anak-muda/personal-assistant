from typing import Optional

from psycopg_pool import AsyncConnectionPool

from constants.log import LOGGER


# Telegram redelivers an update when the webhook does not answer 200 in time.
# Our handler can legitimately run 20-40s (cold start + LLM + Sheets), so a slow
# turn must not become a second `log_spending` row in the user's sheet.
DEDUP_DDL = """
CREATE TABLE IF NOT EXISTS processed_updates (
    update_id  BIGINT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def setup_dedup(pool: AsyncConnectionPool) -> None:
    """Create the dedup table. Idempotent; called from scripts/init_db.py."""
    async with pool.connection() as conn:
        await conn.execute(DEDUP_DDL)


async def claim_update(pool: Optional[AsyncConnectionPool], update_id: int) -> bool:
    """Claim an update for processing.

    Returns True when this process won the claim and should handle the update,
    False when it was already claimed — i.e. this is a Telegram retry.

    Claiming happens *before* the work, not after, so a crash mid-turn leaves
    the update consumed. That is the safer failure: a retry storm would double
    every side effect (spending rows, blast messages) with no way to undo them.

    With no pool (local polling, or DATABASE_URL unset) dedup is skipped —
    long polling acknowledges via `offset` and never redelivers.
    """
    if pool is None:
        return True

    try:
        async with pool.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO processed_updates (update_id) VALUES (%s) "
                "ON CONFLICT (update_id) DO NOTHING",
                (update_id,),
            )
            return cur.rowcount == 1
    except Exception as e:
        # A dedup outage must not take the bot down. Processing a duplicate is
        # worse than usual here, but dropping every message is worse still.
        LOGGER.error(f"Dedup check failed for update {update_id}: {e}", exc_info=True)
        return True
