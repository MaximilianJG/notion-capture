"""
Prompt Loader - Loads and renders prompt templates from files
"""
from pathlib import Path
from functools import lru_cache

PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """
    Load a prompt template from file.
    Templates are cached for performance.
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text()


def render_prompt(name: str, **kwargs) -> str:
    """
    Load and render a prompt template with variables.
    
    Args:
        name: Template name (without .txt extension)
        **kwargs: Variables to substitute in the template
        
    Returns:
        Rendered prompt string
    """
    template = load_prompt(name)
    return template.format(**kwargs)

