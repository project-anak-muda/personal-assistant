from fastapi import APIRouter

from routers.single_agent import single_agent_router


all_router = APIRouter()

all_router.include_router(single_agent_router)
