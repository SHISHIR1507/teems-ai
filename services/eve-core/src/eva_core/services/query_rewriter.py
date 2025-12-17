import os
import json
import re
from typing import Optional
from dotenv import load_dotenv
import google.generativeai as genai

from .message_service import MessageService

load_dotenv()

class QueryRewriterService:
    def __init__(self, message_service: MessageService):
        self.message_service = message_service
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    def _clean_json_output(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()
        return text
    
    async def rewrite_query(
        self,
        original_query: str,
        tenant_id: str,
        conversation_id: Optional[str] = None,
        limit: int = 3
    ) -> dict:
        """
        Rewrite query using conversation context.
        Returns: {"rewritten_query": str, "needs_internet": bool}
        """
        # If no conversation_id, return original
        if not conversation_id or conversation_id == "string":
            return {
                "rewritten_query": original_query,
                "needs_internet": False
            }
        
        # Get conversation history
        messages = await self.message_service.get_recent_messages(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            limit=limit
        )
        
        # If no history, return original 
        if not messages:
            return {
                "rewritten_query": original_query,
                "needs_internet": False
            }
        
        conversation_text = ""
        
        # Process messages in pairs (user -> assistant)
        for i in range(0, len(messages) - 1, 2):
            if i + 1 < len(messages):
                user_msg = messages[i]
                assistant_msg = messages[i + 1]
                
                if user_msg.role == "user" and assistant_msg.role == "assistant":
                    conversation_text += f"User question: {user_msg.content or ''}\n"
                    conversation_text += f"Rewritten question: {user_msg.rewritten_content or user_msg.content or ''}\n"
                    if assistant_msg.content:
                        conversation_text += f"Assistant answer: {assistant_msg.content}\n"
                    conversation_text += "\n"
        
        prompt = f"""
        You are a query understanding and rewriting assistant.
        Your job has TWO responsibilities:

        1. Rewrite the user's current question into a standalone, clear,
        and unambiguous question that can be understood without seeing
        the previous conversation.

        2. Decide whether answering this question requires information
        from the public internet (e.g., recent, current, real-time,
        news, trends), or whether it can be answered entirely using
        the provided internal document/context.

        You are given:
        - A short conversation history (user questions and assistant answers)
        - The user's current question

        Conversation history:
        {conversation_text}

        Current user question:
        "{original_query}"

        Instructions for rewriting:
        - If the current question is already clear and complete, return it unchanged.
        - If the question contains references like "it", "they", "this", "that", or similar,
        replace them with the specific entities or concepts they refer to.
        - Use information from previous assistant answers to resolve references.
        - Preserve the original intent of the user's question.
        - Do NOT add new information or assumptions.
        - Do NOT answer the question.
        - Return ONLY the rewritten question, and nothing else.

        
        Instructions for routing:
        - Set needs_internet = true ONLY if the question is inherently
        about external, public, or time-dependent information that
        would normally require searching the web, such as:
        • recent or changing facts
        • real-time or time-sensitive data
        • public events, news, trends, prices, benchmarks, or comparisons
        • information that cannot reasonably be inferred from prior discussion

        - Set needs_internet = false if the question appears answerable
        by reasoning over information that has already been discussed
        in the conversation or is assumed to exist in the internal content,
        even if explanation, summarization, or interpretation is required.

        - If the question refers to previously mentioned topics, entities,
        or details (e.g., "this", "that", "they", "the document"),
        assume needs_internet = false.

        - The decision should be based on the nature and intent of the
        question, not on verifying the availability of information.

        - When uncertain, prefer needs_internet = false.

        Respond STRICTLY in valid JSON with the following format:

        {{
        "rewritten_query": "<standalone rewritten question>",
        "needs_internet": true or false
        }}
        """
        
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        try:
            response = model.generate_content(prompt)
            
            print("RAW MODEL OUTPUT:")
            print(response.text)
            
            cleaned = self._clean_json_output(response.text)
            result = json.loads(cleaned)
            return result
        except Exception as e:
            print(f"Query rewriting failed: {e}")

            return {
                "rewritten_query": original_query,
                "needs_internet": False
            }