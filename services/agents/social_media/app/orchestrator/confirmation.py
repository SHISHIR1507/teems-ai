"""
Natural-language confirmation detector. No manual anchors — uses LLM to infer if user confirmed.
"""
import re
from app.core.config import get_settings


def _call_llm(prompt: str, system: str = "") -> str:
    s = get_settings()
    import requests
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    url = f"{s.aiml_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {s.aiml_api_key}", "Content-Type": "application/json"}
    body = {"model": s.llm_model, "messages": messages, "max_tokens": 64}
    r = requests.post(url, json=body, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    choice = data.get("choices") or []
    if not choice:
        return ""
    return (choice[0].get("message") or {}).get("content") or ""


def user_confirmed_posting(user_message: str, last_assistant_message: str = "") -> bool:
    """
    Return True if the user message clearly confirms they want to post (e.g. yes, go ahead, post it).
    Uses LLM; no keyword anchors.
    """
    if not (user_message or "").strip():
        return False
    system = "You detect if the user explicitly agreed to post content (e.g. yes, go ahead, post it, sure, do it). Answer only YES or NO."
    prompt = f"Assistant asked: {last_assistant_message or '(none)'}\nUser replied: {user_message}\nDid user confirm posting? YES or NO."
    raw = _call_llm(prompt, system)
    return "yes" in raw.strip().lower()
