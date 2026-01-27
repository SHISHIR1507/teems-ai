"""
Agent recommendation engine
Uses embedding similarity to recommend specialized agents based on conversation context
"""
import sys
from pathlib import Path
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim
from loguru import logger

from .schemas import RecommendationItem
from ..agent_manager_client import check_agent_assignment

# Load model once at startup (same as action recommendations)
model = SentenceTransformer('BAAI/bge-base-en-v1.5')

# Cache for agent specs and embeddings
_agent_specs_cache: List[dict] = []
_agent_embeddings_cache = None


def _load_agent_specs() -> List[dict]:
    """Load all agent specs from markdown files"""
    global _agent_specs_cache
    
    if _agent_specs_cache:
        return _agent_specs_cache
    
    # Add agent directory to path
    agent_dir = Path(__file__).parent.parent.parent.parent / "agent"
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))
    
    try:
        from resources.agent_loader import list_available_agents, load_agent_spec
        
        agent_ids = [agent['id'] for agent in list_available_agents()]
        _agent_specs_cache = []
        
        for agent_id in agent_ids:
            try:
                spec = load_agent_spec(agent_id)
                # agent_manager_id is now extracted by load_agent_spec
                _agent_specs_cache.append(spec)
            except Exception as e:
                logger.warning(f"Failed to load agent spec for {agent_id}: {e}")
                continue
        
        return _agent_specs_cache
    except ImportError as e:
        logger.error(f"Failed to import agent_loader: {e}")
        return []


def _get_agent_embeddings() -> np.ndarray:
    """Get embeddings for all agents (cached)"""
    global _agent_embeddings_cache
    
    if _agent_embeddings_cache is not None:
        return _agent_embeddings_cache
    
    agent_specs = _load_agent_specs()
    
    # Create text representations for embedding
    # Format: "{agent_name} {first_paragraph_of_description}"
    agent_texts = []
    for spec in agent_specs:
        # Get first paragraph from "What It Does" section
        content = spec.get('content', '')
        if '## What It Does' in content:
            parts = content.split('## What It Does', 1)
            if len(parts) > 1:
                description = parts[1].split('\n\n')[0].strip() if '\n\n' in parts[1] else parts[1][:200]
            else:
                description = content[:200]
        else:
            description = content[:200]
        
        agent_text = f"{spec.get('name', '')} {description}"
        agent_texts.append(agent_text)
    
    if not agent_texts:
        _agent_embeddings_cache = np.array([])
        return _agent_embeddings_cache
    
    # Generate embeddings
    _agent_embeddings_cache = model.encode(agent_texts, convert_to_numpy=True)
    return _agent_embeddings_cache


async def recommend_agents(
    query: str,
    tenant_id: str,
    user_id: str,
    auth_token: str,
    k: int = 2
) -> List[RecommendationItem]:
    """
    Recommend agents based on conversation context.
    
    Args:
        query: Combined user message + Eve's reply
        tenant_id: Tenant ID from authenticated user
        user_id: User ID (sub) from authenticated user
        auth_token: Auth0 JWT token for authentication
        k: Number of agent recommendations to return
    
    Returns:
        List of RecommendationItem objects with agent recommendations
    """
    agent_specs = _load_agent_specs()
    
    if not agent_specs:
        logger.warning("No agent specs available for recommendations")
        return []
    
    # Get embeddings
    agent_embeddings = _get_agent_embeddings()
    
    if agent_embeddings.size == 0:
        return []
    
    # Encode query
    query_embedding = model.encode(query, convert_to_numpy=True)
    
    # Calculate similarity scores
    scores = cos_sim(query_embedding, agent_embeddings)[0].numpy()
    
    # Get top k candidates
    top_indices = np.argsort(scores)[::-1][:k * 2]  # Get more candidates for filtering
    
    recommendations = []
    
    for idx in top_indices:
        if idx >= len(agent_specs):
            continue
            
        spec = agent_specs[idx]
        score = float(scores[idx])
        
        # Skip if score is too low (threshold: 0.15)
        if score < 0.15:
            continue
        
        agent_id = spec.get('id')
        agent_name = spec.get('name', agent_id)
        agent_manager_id = spec.get('agent_manager_id', '').strip() if spec.get('agent_manager_id') else ''
        ui_route = spec.get('ui_route', f'/agents/{agent_id}')
        
        # Skip if agent_manager_id is placeholder or missing
        if not agent_manager_id or agent_manager_id == '<uuid-from-agent-manager>':
            logger.debug(f"Skipping {agent_id} - no valid agent_manager_id")
            continue
        
        # Check assignment status
        is_assigned = False
        try:
            is_assigned = await check_agent_assignment(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_manager_id=agent_manager_id,
                auth_token=auth_token
            )
        except Exception as e:
            logger.warning(f"Failed to check assignment for {agent_id}: {e}")
            # Default to not assigned if check fails
        
        # Set label based on assignment status
        if is_assigned:
            action_label = f"Continue chat with {agent_name}"
        else:
            action_label = f"Add {agent_name} to workspace"
        
        recommendations.append(
            RecommendationItem(
                action=action_label,
                score=score,
                id=agent_id,
                type="agent",
                agent_id=agent_id,
                agent_manager_id=agent_manager_id,
                agent_name=agent_name,
                is_assigned=is_assigned,
                ui_route=ui_route,
                click_action="navigate"
            )
        )
        
        # Stop if we have enough recommendations
        if len(recommendations) >= k:
            break
    
    return recommendations
