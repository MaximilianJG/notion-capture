"""
Logging utilities for AI operations
"""

# Enable detailed AI logging
AI_DEBUG_LOGGING = True


def log_ai_prompt(method_name: str, prompt: str):
    """Log AI prompt to terminal"""
    if AI_DEBUG_LOGGING:
        print(f"\n{'='*60}")
        print(f"🤖 AI PROMPT [{method_name}]")
        print(f"{'='*60}")
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
        print(f"{'='*60}\n")


def log_ai_response(method_name: str, response: str):
    """Log AI response to terminal"""
    if AI_DEBUG_LOGGING:
        print(f"\n{'-'*60}")
        print(f"📨 AI RESPONSE [{method_name}]")
        print(f"{'-'*60}")
        print(response[:2000] + "..." if len(response) > 2000 else response)
        print(f"{'-'*60}\n")

