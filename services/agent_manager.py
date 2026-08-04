from typing import Optional

from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from models.llm import get_model
from services.tools import TOOLS
from services.middlewares.compile import get_middlewares
from constants.prompt import SINGLE_AGENT_SYSTEM_TEMPLATE


async def make_graph_single(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> CompiledStateGraph:
    """
    Create the single agent that handles all requests.

    The checkpointer is injected so the caller owns its connection pool and can
    keep it open for as long as the agent is used — see
    `services.checkpointer.checkpointer_scope`. Defaults to InMemorySaver so
    ad-hoc scripts and tests can build an agent without a database.
    """
    model = get_model()
    middlewares = get_middlewares([tool.name for tool in TOOLS])

    single_agent = create_agent(
        model,
        tools=TOOLS,
        system_prompt=SINGLE_AGENT_SYSTEM_TEMPLATE,
        checkpointer=checkpointer or InMemorySaver(),
        middleware=middlewares,
    )

    return single_agent
