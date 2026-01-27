"""
Agent specification loader for Eve
"""
import os
from pathlib import Path
from typing import List, Dict, Optional
import re

# Get the resources directory path
RESOURCES_DIR = Path(__file__).parent
AGENTS_DIR = RESOURCES_DIR / "agents"


def parse_frontmatter(content: str) -> tuple[Dict, str]:
    """
    Parse YAML frontmatter from markdown content.
    
    Args:
        content: Markdown content with optional frontmatter
        
    Returns:
        Tuple of (metadata dict, content without frontmatter)
    """
    # Check if content starts with frontmatter
    if not content.startswith('---'):
        return {}, content
    
    # Split frontmatter and content
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    
    frontmatter = parts[1].strip()
    main_content = parts[2].strip()
    
    # Parse frontmatter (simple key: value format)
    metadata = {}
    for line in frontmatter.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            metadata[key.strip()] = value.strip()
    
    return metadata, main_content


def load_agent_spec(agent_id: str) -> Dict:
    """
    Load an agent specification from resources/agents/
    
    Args:
        agent_id: ID of the agent (e.g., "ugc_creator")
        
    Returns:
        Dictionary with agent metadata and content
        
    Raises:
        FileNotFoundError: If agent spec file doesn't exist
    """
    agent_path = AGENTS_DIR / f"{agent_id}.md"
    
    if not agent_path.exists():
        raise FileNotFoundError(f"Agent spec not found: {agent_path}")
    
    with open(agent_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse frontmatter and content
    metadata, main_content = parse_frontmatter(content)
    
    return {
        'id': metadata.get('id', agent_id),
        'name': metadata.get('name', agent_id.replace('_', ' ').title()),
        'category': metadata.get('category', 'general'),
        'status': metadata.get('status', 'available'),
        'ui_route': metadata.get('ui_route', f'/agents/{agent_id}'),
        'agent_manager_id': metadata.get('agent_manager_id', '').strip(),
        'content': main_content,
        'full_text': content
    }


def list_available_agents() -> List[Dict]:
    """
    List all available agents with their metadata.
    
    Returns:
        List of agent dictionaries with basic info
    """
    agents = []
    
    # Find all .md files in agents directory
    for agent_file in AGENTS_DIR.glob('*.md'):
        # Skip README
        if agent_file.name.lower() == 'readme.md':
            continue
        
        agent_id = agent_file.stem
        try:
            agent_spec = load_agent_spec(agent_id)
            agents.append({
                'id': agent_spec['id'],
                'name': agent_spec['name'],
                'category': agent_spec['category'],
                'status': agent_spec['status']
            })
        except Exception as e:
            print(f"⚠️  Failed to load agent {agent_id}: {e}")
            continue
    
    return agents


def find_agents_by_category(category: str) -> List[Dict]:
    """
    Find agents by category.
    
    Args:
        category: Category to filter by (e.g., "content_creation", "productivity")
        
    Returns:
        List of matching agent dictionaries
    """
    all_agents = list_available_agents()
    return [a for a in all_agents if a['category'] == category]


def find_agents_by_keyword(keyword: str) -> List[Dict]:
    """
    Find agents by searching their content for keywords.
    
    Args:
        keyword: Keyword to search for
        
    Returns:
        List of matching agent dictionaries with relevance
    """
    keyword_lower = keyword.lower()
    matching_agents = []
    
    for agent_file in AGENTS_DIR.glob('*.md'):
        if agent_file.name.lower() == 'readme.md':
            continue
        
        agent_id = agent_file.stem
        try:
            agent_spec = load_agent_spec(agent_id)
            content_lower = agent_spec['content'].lower()
            
            # Count keyword occurrences
            occurrences = content_lower.count(keyword_lower)
            
            if occurrences > 0:
                matching_agents.append({
                    'id': agent_spec['id'],
                    'name': agent_spec['name'],
                    'category': agent_spec['category'],
                    'relevance': occurrences
                })
        except Exception as e:
            continue
    
    # Sort by relevance
    matching_agents.sort(key=lambda x: x['relevance'], reverse=True)
    return matching_agents


def get_agent_summary(agent_id: str) -> str:
    """
    Get a brief summary of an agent (first paragraph after title).
    
    Args:
        agent_id: ID of the agent
        
    Returns:
        Brief summary text
    """
    try:
        agent_spec = load_agent_spec(agent_id)
        content = agent_spec['content']
        
        # Extract first paragraph after "## What It Does"
        match = re.search(r'## What It Does\s+(.+?)(?=\n##|\Z)', content, re.DOTALL)
        if match:
            summary = match.group(1).strip()
            # Get first paragraph
            first_para = summary.split('\n\n')[0]
            return first_para
        
        return f"{agent_spec['name']} agent"
    except Exception:
        return ""


def build_agents_context() -> str:
    """
    Build a context string about all available agents for Eve's system prompt.
    
    Returns:
        Formatted string describing all agents
    """
    agents = list_available_agents()
    
    if not agents:
        return ""
    
    context_parts = ["## Available Agents\n"]
    context_parts.append("I can recommend these specialized agents to help with specific tasks:\n")
    
    # Group by category
    categories = {}
    for agent in agents:
        cat = agent['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(agent)
    
    # Format by category
    for category, cat_agents in categories.items():
        cat_name = category.replace('_', ' ').title()
        context_parts.append(f"\n### {cat_name}")
        
        for agent in cat_agents:
            summary = get_agent_summary(agent['id'])
            context_parts.append(f"- **{agent['name']}**: {summary}")
    
    return '\n'.join(context_parts)


if __name__ == "__main__":
    # Test the agent loader
    print("Testing agent loader...")
    print("\n" + "="*50)
    print("Available Agents:")
    print("="*50)
    
    agents = list_available_agents()
    for agent in agents:
        print(f"- {agent['name']} ({agent['category']}) - {agent['status']}")
    
    print("\n" + "="*50)
    print("Agent Context for Eve:")
    print("="*50)
    context = build_agents_context()
    print(context[:500] + "...")
    
    print("\n" + "="*50)
    print("Search Test (keyword: 'video'):")
    print("="*50)
    results = find_agents_by_keyword('video')
    for result in results:
        print(f"- {result['name']} (relevance: {result['relevance']})")
