"""
Prompt template loader for Eve
"""
import os
from pathlib import Path
from typing import List, Optional

# Get the resources directory path
RESOURCES_DIR = Path(__file__).parent
PROMPTS_DIR = RESOURCES_DIR / "prompts"


def load_prompt(name: str) -> str:
    """
    Load a prompt template from resources/prompts/
    
    Args:
        name: Name of the prompt file (without .md extension)
        
    Returns:
        Content of the prompt file
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / f"{name}.md"
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def build_system_prompt(base: str = "eve", context_prompts: Optional[List[str]] = None) -> str:
    """
    Build a complete system prompt by combining base prompt with context-specific prompts.
    
    Args:
        base: Name of the base prompt (default: "eve")
        context_prompts: List of additional prompt names to include based on context
        
    Returns:
        Combined system prompt
        
    Example:
        >>> build_system_prompt("eve", ["research", "database"])
        # Returns eve.md + research.md + database.md combined
    """
    if context_prompts is None:
        context_prompts = []
    
    # Load base prompt
    try:
        prompt_parts = [load_prompt(base)]
    except FileNotFoundError:
        print(f"⚠️  Base prompt '{base}' not found, using empty base")
        prompt_parts = []
    
    # Load context prompts
    for context in context_prompts:
        try:
            prompt_parts.append(load_prompt(context))
        except FileNotFoundError:
            print(f"⚠️  Context prompt '{context}' not found, skipping")
            continue
    
    # Combine with double newlines
    return "\n\n".join(prompt_parts)


def detect_context_prompts(tools_used: List[str]) -> List[str]:
    """
    Detect which context prompts to load based on tools used in conversation.
    
    Args:
        tools_used: List of tool names that were called
        
    Returns:
        List of prompt names to load
    """
    context_prompts = []
    
    # Map tool patterns to prompt files
    tool_prompt_map = {
        "tavily": "research",
        "search": "research",
        "query": "database",
        "postgres": "database",
        "sql": "database",
        "query_knowledge_base": "documents",
        "list_documents": "documents",
        "knowledge_base": "documents",
    }
    
    # Check which prompts are needed
    prompts_needed = set()
    for tool in tools_used:
        tool_lower = tool.lower()
        for pattern, prompt in tool_prompt_map.items():
            if pattern in tool_lower:
                prompts_needed.add(prompt)
    
    return list(prompts_needed)


def get_initial_system_prompt() -> str:
    """
    Get the initial system prompt with all context loaded.
    Used at startup before any tools are called.
    
    Returns:
        Complete system prompt with all contexts
    """
    return build_system_prompt(
        base="eve",
        context_prompts=["research", "database", "documents"]
    )


if __name__ == "__main__":
    # Test the prompt loader
    print("Testing prompt loader...")
    print("\n" + "="*50)
    print("Base prompt (eve):")
    print("="*50)
    print(load_prompt("eve")[:200] + "...")
    
    print("\n" + "="*50)
    print("Full system prompt:")
    print("="*50)
    full_prompt = get_initial_system_prompt()
    print(f"Total length: {len(full_prompt)} characters")
    print(f"First 300 chars:\n{full_prompt[:300]}...")
