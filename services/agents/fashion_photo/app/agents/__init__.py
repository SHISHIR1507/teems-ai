"""
CrewAI agents for Fashion Photo Agent
"""
from app.agents.fashion_director import create_fashion_director_agent
from app.agents.scene_consultant import create_scene_consultant_agent
from app.agents.image_generator_agent import create_image_generator_agent
from app.agents.editor_agent import create_editor_agent

__all__ = [
    "create_fashion_director_agent",
    "create_scene_consultant_agent",
    "create_image_generator_agent",
    "create_editor_agent",
]
