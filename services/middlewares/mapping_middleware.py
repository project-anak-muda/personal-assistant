from typing import List
from langchain.agents.middleware import (
    ModelCallLimitMiddleware, ToolCallLimitMiddleware, 
    SummarizationMiddleware, HumanInTheLoopMiddleware
)

from models.llm import get_model
from constants.config import MIDDLEWARE_LIST_TOOLS


def compile_hitl(
    tools_names: List[str],
) -> HumanInTheLoopMiddleware:
    # Build interrupt_on config for all tools at once
    interrupt_on = {}
    description_parts = []
    
    for tool_name in tools_names:
        if tool_name in MIDDLEWARE_LIST_TOOLS:
            desc_tool = MIDDLEWARE_LIST_TOOLS.get(tool_name)
            
            # Add this tool to the interrupt config
            interrupt_on[tool_name] = True
            description_parts.append(f"{tool_name}: {desc_tool}")
    
    # Only create ONE middleware instance if we have any tools to monitor
    if interrupt_on:
        # Special case for execute_sql if needed
        if "execute_sql" in tools_names:
            interrupt_on["execute_sql"] = {"allowed_decisions": ["approve", "reject"]}
        
        # Combine descriptions
        description_prefix = "\n".join(description_parts)
        
        hitl = HumanInTheLoopMiddleware(
            interrupt_on=interrupt_on,
            description_prefix=description_prefix,
        )
        
        return hitl
    
MAPPING_MIDDLEWARE = {
    "model_call_limit": \
        ModelCallLimitMiddleware(
            thread_limit=10,
            run_limit=5,
            exit_behavior="end",
        ),
    "tool_call_limit": \
        ToolCallLimitMiddleware(
            tool_name="rag_search",
            thread_limit=5,
            run_limit=3,
        ),
    "summary_chat": \
        SummarizationMiddleware(
            model=get_model(),
            trigger=("tokens", 4000),
            keep=("messages", 20),
        ),
    "hitl": \
        compile_hitl,
}