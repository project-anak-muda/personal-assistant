import os

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI


def get_model(provider: str = "local"):
    provider = provider.lower()
    
    if provider == "google":
        return get_model_google()
    elif provider == "local":
        return get_model_local()
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def get_model_google() -> ChatGoogleGenerativeAI:
    llm = ChatGoogleGenerativeAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        model=os.getenv("GEMINI_MODEL_NAME"),
        temperature=0.4,
        top_k=32,
        top_p=1,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        streaming=True,
    )
    return llm

def get_model_local() -> ChatOpenAI:
    llm = ChatOpenAI(
        base_url=os.getenv("LOCAL_LLM_BASE_URL"),
        api_key=os.getenv("LOCAL_LLM_API_KEY"),
        model=os.getenv("LOCAL_LLM_MODEL"),
        temperature=0.4,
        max_retries=2,
        streaming=True,
    )
    return llm