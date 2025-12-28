"""
OpenAI Client - Lazy initialization
"""
from typing import Optional
from openai import OpenAI
from app.config import get_openai_api_key

_client: Optional[OpenAI] = None


def get_openai_client() -> Optional[OpenAI]:
    """Get or create OpenAI client (lazy initialization)"""
    global _client
    
    if _client is None:
        api_key = get_openai_api_key()
        if api_key:
            _client = OpenAI(api_key=api_key)
    
    return _client

