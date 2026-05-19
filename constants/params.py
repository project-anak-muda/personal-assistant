from typing import List, Optional
from pydantic import BaseModel, Field


class ChatbotParams(BaseModel):
    session_id: str = Field(description="Conversation/thread id")
    query: str = Field(description="User's text input")
    image_base64: Optional[str] = Field(
        default=None,
        description="Optional base64-encoded image (no data URI prefix needed)",
    )
    image_mime: Optional[str] = Field(
        default="image/jpeg",
        description="MIME type of the image, e.g. image/jpeg or image/png",
    )
    
class SplitItem(BaseModel):
    name: str = Field(description="Name of the item")
    price: float = Field(description="Price of the item (before tax/service)")
    shared_by: List[str] = Field(
        description="Names of participants who consumed this item"
    )