import uuid

from typing import Dict, Any, Optional
from langgraph.graph.state import CompiledStateGraph
from fastapi import ( 
    APIRouter, HTTPException, Request,
    Depends, Form, File, UploadFile,
)

from constants.log import LOGGER
from utils.helpers import extract_agent_response, build_user_message


single_agent_router = APIRouter(
    tags=["SINGLE AGENT ENDPOINT"],
    responses={404: {"description": "Not found"}},
    prefix="/single-agent"
)

def get_single_agent(request: Request) -> CompiledStateGraph:
    """Dependency to get tools from app context"""
    if not hasattr(request.app, 'context') or 'single_agent' not in request.app.context:
        raise HTTPException(
            status_code=503,
            detail="Tools not available"
        )
    return request.app.context['single_agent']

@single_agent_router.post("/generate-answer")
async def generate_answer(
    session_id: str = Form(..., description="Conversation/thread id"),
    query: str = Form(..., description="User's text input"),
    image: Optional[UploadFile] = File(
        default=None,
        description="Optional image of the bill (jpeg/png).",
    ),
    image_base64: Optional[str] = Form(
        default=None,
        description="Alternative to `image`: base64-encoded image string.",
    ),
    image_mime: Optional[str] = Form(
        default="image/jpeg",
        description="MIME type used when `image_base64` is provided.",
    ),
    single_agent: CompiledStateGraph = Depends(get_single_agent),
) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())

    try:
        image_bytes = await image.read() if image is not None else None
        if image is not None and image.content_type:
            image_mime = image.content_type

        user_message = build_user_message(
            query=query,
            image_bytes=image_bytes,
            image_base64=image_base64,
            image_mime=image_mime or "image/jpeg",
        )

        config = {
            "configurable": {
                "thread_id": session_id,
            },
            "run_name": f"{session_id}_{run_id}",
            "run_id": run_id,
        }

        response = await single_agent.ainvoke(
            {"messages": [user_message]},
            config=config,
        )

        return extract_agent_response(response, session_id, run_id)

    except Exception as e:
        LOGGER.error(f"Error in generate_answer: {e}", exc_info=True)
        return {
            "status": "error",
            "data": {
                "requires_approval": False,
                "session_id": session_id,
                "run_id": run_id,
                "error": str(e),
                "final_answer": f"Internal server error: {str(e)}",
            },
        }