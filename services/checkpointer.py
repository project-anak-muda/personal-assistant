import os

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from constants.log import LOGGER


CONNECTION_KWARGS = {
    "autocommit": True,
    # Disable server-side prepared statements. Neon's pooled endpoint (and any
    # PgBouncer in transaction mode) hands the same backend to different
    # sessions, so a statement prepared by one request may be missing in the
    # next. At a few requests per day the lost caching costs us nothing.
    "prepare_threshold": None,
    # AsyncPostgresSaver reads rows by column name.
    "row_factory": dict_row,
}


def _build_pool(conn_string: str) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        conninfo=conn_string,
        # An idle container should hold no connection open: Neon autosuspends,
        # and reconnecting is cheaper than discovering a dead socket mid-request.
        min_size=0,
        max_size=2,
        open=False,
        # After Neon wakes from autosuspend a pooled connection is usually
        # stale, so revalidate before handing one out.
        check=AsyncConnectionPool.check_connection,
        kwargs=CONNECTION_KWARGS,
    )


@asynccontextmanager
async def pool_scope() -> AsyncIterator[Optional[AsyncConnectionPool]]:
    """Yield an open connection pool, or None when DATABASE_URL is unset.

    One pool serves everything that needs Postgres — the checkpointer and the
    webhook's update dedup — so callers that need both open it once here rather
    than each building their own.
    """
    conn_string = os.getenv("DATABASE_URL")

    if not conn_string:
        LOGGER.warning(
            "DATABASE_URL is not set — falling back to InMemorySaver. "
            "Conversation state will be lost on restart."
        )
        yield None
        return

    pool = _build_pool(conn_string)
    await pool.open()
    LOGGER.info("Postgres pool opened")

    try:
        yield pool
    finally:
        await pool.close()
        LOGGER.info("Postgres pool closed")


def build_checkpointer(pool: Optional[AsyncConnectionPool]) -> BaseCheckpointSaver:
    """Wrap an open pool in a checkpointer, or fall back to in-memory state."""
    return AsyncPostgresSaver(pool) if pool is not None else InMemorySaver()


@asynccontextmanager
async def checkpointer_scope() -> AsyncIterator[BaseCheckpointSaver]:
    """Yield a checkpointer whose connection pool stays open for the caller's lifetime.

    The pool is owned here rather than inside `make_graph_single` because the
    agent outlives any single call — closing the pool when the graph is built
    would leave every later `ainvoke` without a connection.

    Falls back to InMemorySaver when DATABASE_URL is unset so local runs work
    without a database. That fallback drops all conversation state on restart;
    it is not meant for deployed environments.
    """
    async with pool_scope() as pool:
        yield build_checkpointer(pool)
