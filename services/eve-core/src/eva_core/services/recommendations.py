"""
Action recommendation system for Eve Core
Based on Manasa's recommendation function
"""
import numpy as np
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

# Load model once at startup
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

action_items = [
    # Knowledge / RAG (1-11)
    "Summarize document",
    "Extract insights",
    "Generate outline", 
    "Create summary",
    "Tag content",
    "Find key points",
    "Compare sections",
    "Translate text",
    "Rewrite clearer",
    "Find contradictions",
    "Related documents",
    
    # Data Handling (12-19)
    "Convert to table",
    "Export as CSV",
    "Clean dataset",
    "Analyze data",
    "Detect anomalies",
    "Show trends",
    "Visualize data",
    "Normalize fields",
    
    # Workflows (20-25)
    "Create workflow",
    "Schedule workflow",
    "Add approval",
    "Draft workflow",
    "Review workflow",
    "Trigger workflow",
    
    # Agents (26-32)
    "Run agent",
    "Create agent",
    "Edit agent",
    "Test agent",
    "Publish agent",
    "Monitor agent",
    "Clone agent",
    
    # Chat / Persona (33-36)
    "Refine response",
    "Improve answer",
    "Explain deeper",
    "Ask follow-up",
    
    # Platform (37-43)
    "Open dashboard",
    "Team settings",
    "Invite teammates",
    "View activity",
    "Check limits",
    "Upgrade plan",
    "Add integrations"
]

# Embed all action items once
embeddings = model.encode(action_items, convert_to_numpy=True)
from ..schemas.rag import RecommendationItem
def recommend_actions(query: str, k: int = 3, threshold: float = 0.25) -> list[RecommendationItem]:
    
    # Encode user query
    q_emb = model.encode(query, convert_to_numpy=True)
    
    # Calculate similarity scores
    scores = cos_sim(q_emb, embeddings)[0].numpy()
    
    # Get top k indices
    idx = np.argsort(scores)[::-1][:k]
    
    # Filter by threshold and format results
    filtered_results = [
        RecommendationItem( 
            action=action_items[i],
            score=float(scores[i]),
            id=i
        )
        for i in idx if scores[i] >= threshold
    ]
    
    # Return at least one result if none meet threshold
    if not filtered_results:
        return [RecommendationItem(
            action="No relevant actions found",
            score=0.0,
            id=-1
        )]

    return filtered_results