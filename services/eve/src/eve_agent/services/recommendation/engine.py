"""
Action recommendation system for Eve Core
"""
import numpy as np
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

from .schemas import RecommendationItem

# Load model once at startup
model = SentenceTransformer('BAAI/bge-base-en-v1.5')

# Structured action definitions with metadata
ACTIONS = [
    # General Actions
    {"id": "explain_deeper", "label": "Explain deeper", "domain": "general", "category": "explore",
     "keywords": ["explain", "detail", "more", "deeper", "elaborate"], "excludes": ["explain_deeper"]},
    {"id": "simplify_answer", "label": "Simplify answer", "domain": "general", "category": "explore",
     "keywords": ["simplify", "simple", "easier", "basic"], "excludes": ["simplify_answer"]},
    {"id": "give_examples", "label": "Give examples", "domain": "general", "category": "explore",
     "keywords": ["example", "instance", "sample", "case"], "excludes": ["give_examples"]},
    {"id": "ask_followup", "label": "Ask follow-up", "domain": "general", "category": "explore",
     "keywords": ["question", "ask", "clarify", "more"], "excludes": ["ask_followup"]},
    {"id": "provide_checklist", "label": "Provide checklist", "domain": "general", "category": "create",
     "keywords": ["checklist", "list", "steps", "todo"], "excludes": ["provide_checklist"]},
    
    # Internet/Research Actions
    {"id": "search_web", "label": "Search the web", "domain": "internet", "category": "explore",
     "keywords": ["search", "find", "look up", "research", "google"], "excludes": ["search_web"]},
    {"id": "find_competitors", "label": "Find competitors", "domain": "internet", "category": "analyze",
     "keywords": ["competitor", "rival", "competition", "alternative"], "excludes": ["find_competitors"]},
    {"id": "verify_claim", "label": "Verify this claim", "domain": "internet", "category": "verify",
     "keywords": ["verify", "check", "confirm", "validate", "fact"], "excludes": ["verify_claim"]},
    {"id": "find_recent_news", "label": "Find recent news", "domain": "internet", "category": "explore",
     "keywords": ["news", "recent", "latest", "update", "current"], "excludes": ["find_recent_news"]},
    {"id": "find_reviews", "label": "Find customer reviews", "domain": "internet", "category": "analyze",
     "keywords": ["review", "feedback", "opinion", "rating", "customer"], "excludes": ["find_reviews"]},
    {"id": "research_market", "label": "Research market", "domain": "internet", "category": "analyze",
     "keywords": ["market", "industry", "sector", "landscape"], "excludes": ["research_market"]},
    {"id": "look_up_company", "label": "Look up company", "domain": "internet", "category": "explore",
     "keywords": ["company", "business", "organization", "firm"], "excludes": ["look_up_company"]},
    {"id": "find_statistics", "label": "Find statistics", "domain": "internet", "category": "analyze",
     "keywords": ["statistics", "stats", "data", "numbers", "metrics"], "excludes": ["find_statistics"]},
    {"id": "check_pricing", "label": "Check pricing", "domain": "internet", "category": "explore",
     "keywords": ["price", "pricing", "cost", "fee", "rate"], "excludes": ["check_pricing"]},
    
    # Meeting Actions
    {"id": "summarize_meeting", "label": "Summarize meeting", "domain": "meeting", "category": "explore",
     "keywords": ["meeting", "summary", "overview", "recap"], "excludes": ["summarize_meeting"]},
    {"id": "find_decisions", "label": "Find decisions made", "domain": "meeting", "category": "analyze",
     "keywords": ["decision", "decided", "agreed", "conclusion"], "excludes": ["find_decisions"]},
    {"id": "find_action_items", "label": "Find action items", "domain": "meeting", "category": "analyze",
     "keywords": ["action", "todo", "task", "next steps", "follow up"], "excludes": ["find_action_items"]},
    {"id": "find_blockers", "label": "Find blockers", "domain": "meeting", "category": "analyze",
     "keywords": ["blocker", "issue", "problem", "challenge", "risk"], "excludes": ["find_blockers"]},
    {"id": "find_deadlines", "label": "Find deadlines", "domain": "meeting", "category": "analyze",
     "keywords": ["deadline", "due", "timeline", "schedule"], "excludes": ["find_deadlines"]},
    {"id": "list_meetings", "label": "List all meetings", "domain": "meeting", "category": "explore",
     "keywords": ["list", "all", "meetings", "show", "view"], "excludes": ["list_meetings"]},
    {"id": "find_who_said", "label": "Find who said this", "domain": "meeting", "category": "explore",
     "keywords": ["who", "said", "mentioned", "speaker"], "excludes": ["find_who_said"]},
    {"id": "compare_meetings", "label": "Compare meetings", "domain": "meeting", "category": "analyze",
     "keywords": ["compare", "comparison", "versus", "difference"], "excludes": ["compare_meetings"]},
    
    # Database Actions
    {"id": "query_database", "label": "Query database", "domain": "database", "category": "explore",
     "keywords": ["query", "database", "sql", "select", "data"], "excludes": ["query_database"]},
    {"id": "show_stored_data", "label": "Show stored data", "domain": "database", "category": "explore",
     "keywords": ["show", "display", "view", "stored", "saved"], "excludes": ["show_stored_data"]},
    {"id": "export_csv", "label": "Export as CSV", "domain": "database", "category": "export",
     "keywords": ["export", "download", "csv", "file", "save"], "excludes": ["export_csv"]},
    {"id": "analyze_data", "label": "Analyze this data", "domain": "database", "category": "analyze",
     "keywords": ["analyze", "analysis", "insights", "trends"], "excludes": ["analyze_data"]},
    {"id": "compare_data", "label": "Compare data", "domain": "database", "category": "analyze",
     "keywords": ["compare", "comparison", "versus", "difference"], "excludes": ["compare_data"]},
    {"id": "filter_records", "label": "Filter records", "domain": "database", "category": "explore",
     "keywords": ["filter", "where", "condition", "criteria"], "excludes": ["filter_records"]},
    {"id": "show_trends", "label": "Show trends", "domain": "database", "category": "analyze",
     "keywords": ["trend", "pattern", "growth", "change"], "excludes": ["show_trends"]},
]

# Create text representations for embedding
action_texts = [f"{a['label']} {' '.join(a['keywords'])}" for a in ACTIONS]

# Embed all action items once
embeddings = model.encode(action_texts, convert_to_numpy=True)


def detect_domain(tools_used: list[str]) -> str:
    """Detect domain based on tools used in the conversation"""
    if not tools_used:
        return "general"
    
    # Map tool names to domains
    tool_domain_map = {
        "tavily": "internet",
        "search": "internet",
        "query": "database",
        "postgres": "database",
        "sql": "database",
    }
    
    # Check which domain matches the tools used
    for tool in tools_used:
        tool_lower = tool.lower()
        for key, domain in tool_domain_map.items():
            if key in tool_lower:
                return domain
    
    return "general"


def recommend_actions(
    query: str, 
    recent_actions: list[str] = None,
    tools_used: list[str] = None,
    k: int = 3, 
    threshold: float = 0.20
) -> list[RecommendationItem]:
    """
    Recommend actions based on query context, recent actions, and tools used.
    
    Args:
        query: Combined user message + Eve's reply
        recent_actions: List of recently clicked action IDs
        tools_used: List of tool names used in the conversation
        k: Number of recommendations to return
        threshold: Minimum similarity score
    """
    if recent_actions is None:
        recent_actions = []
    if tools_used is None:
        tools_used = []
    
    # Detect domain from tools used
    detected_domain = detect_domain(tools_used)
    
    # Filter candidate actions
    candidate_actions = []
    for i, action in enumerate(ACTIONS):
        # Skip if recently used (last 3 actions)
        if action['id'] in recent_actions[-3:]:
            continue
        
        # Include if domain matches or action is general
        if action['domain'] == detected_domain or action['domain'] == 'general':
            candidate_actions.append((i, action))
    
    # If no candidates after filtering, use all actions
    if not candidate_actions:
        candidate_actions = [(i, action) for i, action in enumerate(ACTIONS)]
    
    # Get embeddings for candidate actions
    candidate_indices = [i for i, _ in candidate_actions]
    candidate_embeddings = embeddings[candidate_indices]
    
    # Encode user query
    q_emb = model.encode(query, convert_to_numpy=True)
    
    # Calculate similarity scores
    scores = cos_sim(q_emb, candidate_embeddings)[0].numpy()
    
    # Apply keyword boosting
    boosted_scores = []
    for idx, (orig_idx, action) in enumerate(candidate_actions):
        score = float(scores[idx])
        
        # Boost if keywords match
        query_lower = query.lower()
        keyword_matches = sum(1 for kw in action['keywords'] if kw in query_lower)
        if keyword_matches > 0:
            score *= (1.0 + 0.1 * keyword_matches)  # 10% boost per keyword match
        
        boosted_scores.append((orig_idx, action, score))
    
    # Sort by score
    boosted_scores.sort(key=lambda x: x[2], reverse=True)
    
    # Filter by threshold and format results
    filtered_results = [
        RecommendationItem(
            action=action['label'],
            score=score,
            id=action['id']
        )
        for orig_idx, action, score in boosted_scores[:k * 2]  # Get more candidates
        if score >= threshold
    ][:k]  # Return top k
    
    # Return at least one result if none meet threshold
    if not filtered_results and boosted_scores:
        best = boosted_scores[0]
        return [RecommendationItem(
            action=best[1]['label'],
            score=best[2],
            id=best[1]['id']
        )]
    
    return filtered_results if filtered_results else []


async def recommend_actions_and_agents(
    query: str,
    tenant_id: str,
    user_id: str,
    auth_token: str,
    recent_actions: list[str] = None,
    tools_used: list[str] = None,
    k_actions: int = 3,
    k_agents: int = 2
) -> list[RecommendationItem]:
    """
    Recommend both actions and agents based on conversation context.
    
    Args:
        query: Combined user message + Eve's reply
        tenant_id: Tenant ID from authenticated user
        user_id: User ID (sub) from authenticated user
        auth_token: Auth0 JWT token for authentication
        recent_actions: List of recently clicked action IDs
        tools_used: List of tool names used in the conversation
        k_actions: Number of action recommendations to return
        k_agents: Number of agent recommendations to return
    
    Returns:
        Combined list of action and agent recommendations, sorted by score
    """
    from .agent_recommender import recommend_agents
    
    # Get action recommendations (sync)
    action_recommendations = recommend_actions(
        query=query,
        recent_actions=recent_actions,
        tools_used=tools_used,
        k=k_actions,
        threshold=0.20
    )
    
    # Set click_action for action recommendations
    for rec in action_recommendations:
        rec.click_action = "chat_followup"
        rec.type = "action"
    
    # Get agent recommendations (async)
    try:
        agent_recommendations = await recommend_agents(
            query=query,
            tenant_id=tenant_id,
            user_id=user_id,
            auth_token=auth_token,
            k=k_agents
        )
    except Exception as e:
        # Log error but continue with action recommendations only
        from loguru import logger
        logger.warning(f"Failed to get agent recommendations: {e}")
        agent_recommendations = []
    
    # Combine both lists
    all_recommendations = list(action_recommendations) + list(agent_recommendations)
    
    # Sort by score (descending)
    all_recommendations.sort(key=lambda x: x.score, reverse=True)
    
    return all_recommendations
