import re
import json
import base64

from datetime import datetime
from langchain.messages import AIMessage
from typing import Any, Dict, List, Optional

from constants.config import TIMEZONE


def parse_amount(raw) -> Optional[float]:
    """Parse a money value that may be a number or a formatted string.

    Handles Indonesian formatting like "Rp5.000.000", "Rp 5.000.000,50",
    "5,000,000", "5000000". Returns None if it can't be parsed.
    """
    if raw in (None, ""):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    s = str(raw).strip()
    # keep only digits, separators, and a leading minus
    s = re.sub(r"[^0-9.,-]", "", s)
    if not s:
        return None

    has_dot = "." in s
    has_comma = "," in s
    if has_dot and has_comma:
        # the rightmost separator is the decimal point; the other is thousands
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # ID style: 5.000.000,50
        else:
            s = s.replace(",", "")                       # EN style: 5,000,000.50
    elif has_comma:
        # comma alone -> treat as thousands separator (IDR usually has no cents)
        s = s.replace(",", "")
    elif has_dot:
        # dot alone: if it looks like a thousands separator, drop it
        if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
            s = s.replace(".", "")
        # otherwise leave it as a real decimal point

    try:
        return float(s)
    except ValueError:
        return None

def _datetime_prefix() -> str:
    now = datetime.now(TIMEZONE)
    return (
        f"[Current datetime: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} "
        f"({now.strftime('%A')})]\n"
    )

def build_user_message(
    query: str,
    image_bytes: Optional[bytes] = None,
    image_base64: Optional[str] = None,
    image_mime: str = "image/jpeg",
) -> Dict[str, Any]:
    """Build a multimodal user message dict for the agent.

    Accepts either raw image bytes (from an UploadFile) or a pre-encoded
    base64 string. The current datetime (Asia/Jakarta) is prepended to the
    query so the agent always has a fresh sense of "now".
    """
    query_with_time = f"{_datetime_prefix()}{query}"

    if image_bytes is not None and not image_base64:
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    if not image_base64:
        return {"role": "user", "content": query_with_time}

    if image_base64.startswith("data:"):
        data_url = image_base64
    else:
        data_url = f"data:{image_mime};base64,{image_base64}"

    content: List[Dict[str, Any]] = [
        {"type": "text", "text": query_with_time},
        {"type": "image_url", "image_url": data_url},
    ]
    return {"role": "user", "content": content}

def extract_agent_response(response: dict, session_id: str = None, run_id: str = None) -> Dict[str, Any]:
    """
    Extract and parse the structured output from agent response.
    Returns a complete, ready-to-return API response.
    
    Args:
        response: The agent response dictionary containing messages
        session_id: Optional session ID for tracking
        run_id: Optional run ID for tracking
        
    Returns:
        Complete API response dictionary ready to return
    """
    # Check for interrupts
    interrupts = response.get('__interrupt__', [])
    
    # Get final AI message
    final_ai_message = next(
        (msg for msg in reversed(response["messages"]) if isinstance(msg, AIMessage)),
        None
    )
    
    # Handle interrupt case (requires approval)
    if interrupts:
        interrupt_data = interrupts[0].value if hasattr(interrupts[0], 'value') else interrupts[0]
        action_requests = interrupt_data.get('action_requests', [])
        action = action_requests[0] if action_requests else {}
        
        return {
            "status": "interrupted",
            "data": {
                "requires_approval": True,
                "session_id": session_id,
                "run_id": run_id,
                "message": f"About to execute: {action.get('name')}",
                "tool_name": action.get('name'),
                "tool_args": action.get('args'),
                "description": action.get('description'),
                "final_answer": final_ai_message.content if final_ai_message else None
            }
        }
    
    # No AI message found
    if not final_ai_message:
        return {
            "status": "error",
            "data": {
                "requires_approval": False,
                "session_id": session_id,
                "run_id": run_id,
                "error": "No AI message found",
                "final_answer": "No AI response found"
            }
        }
    
    # Extract structured output
    structured_output = None
    
    # Method 1: tool_calls (look for ParsingOutput or CoreOutput)
    if hasattr(final_ai_message, 'tool_calls') and final_ai_message.tool_calls:
        for tool_call in final_ai_message.tool_calls:
            if tool_call.get('name') in ['ParsingOutput', 'CoreOutput']:
                structured_output = tool_call.get('args')
                break
    
    # Method 2: function_call in additional_kwargs
    if not structured_output and hasattr(final_ai_message, 'additional_kwargs'):
        function_call = final_ai_message.additional_kwargs.get('function_call')
        if function_call and function_call.get('name') in ['ParsingOutput', 'CoreOutput']:
            try:
                structured_output = json.loads(function_call.get('arguments', '{}'))
            except json.JSONDecodeError:
                pass
    
    # Method 3: Parse content directly
    if not structured_output and hasattr(final_ai_message, 'text') and final_ai_message.text:
        try:
            structured_output = json.loads(final_ai_message.text)
        except (json.JSONDecodeError, TypeError):
            # Content is not JSON, wrap it in CoreOutput format
            structured_output = {
                "type": "info",
                "message": final_ai_message.text
            }
    
    # Return structured response - SUCCESS CASE
    if structured_output:
        # Handle both formats: {data: [...]} or direct list
        if isinstance(structured_output, dict):
            return {
                "status": "success",
                "data": {
                    "requires_approval": False,
                    "session_id": session_id,
                    "run_id": run_id,
                    "final_answer": structured_output.get('message')
                }
            }
        elif isinstance(structured_output, list):
            # Direct list of CoreOutput items
            return {
                "status": "success",
                "data": {
                    "requires_approval": False,
                    "session_id": session_id,
                    "run_id": run_id,
                    "final_answer": structured_output
                }
            }
    
    # Final fallback - ERROR CASE
    return {
        "status": "error",
        "data": {
            "requires_approval": False,
            "session_id": session_id,
            "run_id": run_id,
            "error": "Could not parse structured output",
            "final_answer": "Response format not recognized"
        }
    }