from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import InMemorySaver

from models.llm import get_model
from services.tools import TOOLS
from services.middlewares.compile import get_middlewares
from constants.prompt import SINGLE_AGENT_SYSTEM_TEMPLATE


async def make_graph_single() -> CompiledStateGraph:
    """
    Create the single agent that handles all requests.
    """
    model = get_model()
    checkpointer = InMemorySaver()
    middlewares = get_middlewares([tool.name for tool in TOOLS])
    
    single_agent = create_agent(
        model,
        tools=TOOLS,
        system_prompt=SINGLE_AGENT_SYSTEM_TEMPLATE,
        checkpointer=checkpointer,
        middleware=middlewares,
    )

    return single_agent