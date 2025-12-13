from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import Settings
from ..models import OnboardingState, ConversationMessage
from ..services.llm import LLMService
from ..services.clients import BrandfetchClient, AgentManagerClient
from ..events import EventPublisher
from ..auth import AuthenticatedUser


class StageHandler:
    """Handles stage-specific logic for onboarding flow."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        llm_service: LLMService,
        brandfetch_client: BrandfetchClient,
        agent_manager_client: AgentManagerClient,
        publisher: EventPublisher,
        user: AuthenticatedUser,
    ):
        self.session = session
        self.settings = settings
        self.llm_service = llm_service
        self.brandfetch_client = brandfetch_client
        self.agent_manager_client = agent_manager_client
        self.publisher = publisher
        self.user = user

    async def get_conversation_history(self, conversation_id: str, limit: int = 20) -> list[dict[str, str]]:
        """Get recent conversation history for context."""
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        messages = result.scalars().all()
        # Reverse to get chronological order
        return [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(messages)
        ]

    async def save_message(self, conversation_id: str, role: str, content: str, stage: str | None = None):
        """Save a conversation message."""
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            stage=stage,
        )
        self.session.add(message)
        await self.session.flush()

    async def handle_brand_discovery(
        self, state: OnboardingState, user_message: str
    ) -> tuple[str, bool]:
        """
        Handle Stage 2: Brand Discovery
        Returns: (response_message, stage_completed)
        """
        system_prompt = """You are a friendly onboarding assistant helping users set up their workspace.

Current stage: Brand Discovery

Your task is to ask the user for their website URL. Once they provide a valid website URL (like teems.ai), acknowledge it and let them know we're fetching their brand information.

If they provide an invalid URL, politely ask them to provide a valid website URL and give them an example like "teems.ai".

Keep your responses concise and friendly."""

        # Get conversation history
        history = await self.get_conversation_history(state.conversation_id)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Generate LLM response
        llm_response = await self.llm_service.generate(messages)

        # Check if user message looks like a URL
        is_valid, error_msg = BrandfetchClient.validate_url(user_message)
        
        if is_valid:
            # Extract domain from URL
            from urllib.parse import urlparse
            url_input = user_message.strip()
            if not url_input.startswith(("http://", "https://")):
                url_input = "https://" + url_input
            parsed = urlparse(url_input)
            domain = parsed.netloc or parsed.path.split("/")[0]
            if domain.startswith("www."):
                domain = domain[4:]

            # Call Brandfetch API
            try:
                brand_data = await self.brandfetch_client.fetch_brand(
                    user_message,
                    conversation_id=state.conversation_id,
                    tenant_id=self.user.tenant_id,
                )
                
                # Update state
                state.brand_domain = domain
                state.current_stage = "suggested_teammates"
                
                # Publish event
                channel = f"{self.settings.onboarding_channel_prefix}:{self.user.tenant_id}"
                await self.publisher.publish(
                    channel,
                    {
                        "type": "brandfetch.completed",
                        "step": "brand_discovery",
                        "next_step": "suggested_teammates",
                        "tenant_id": self.user.tenant_id,
                        "conversation_id": state.conversation_id,
                        "domain": brand_data.get("domain"),
                        "name": brand_data.get("name"),
                    },
                )

                response = f"Great! I've fetched your brand information for {domain}. Now let's set up your team."
                await self.save_message(state.conversation_id, "assistant", response, "brand_discovery")
                return response, True
            except Exception as e:
                error_response = f"I encountered an error fetching your brand information. Could you please provide your website URL again? Example: teems.ai"
                await self.save_message(state.conversation_id, "assistant", error_response, "brand_discovery")
                return error_response, False
        else:
            # Invalid URL - use LLM response but guide user
            response = llm_response
            if "example" not in response.lower() and "teems.ai" not in response.lower():
                response += " For example, you could provide a URL like teems.ai"
            await self.save_message(state.conversation_id, "assistant", response, "brand_discovery")
            return response, False

    async def handle_suggested_teammates(
        self, state: OnboardingState, user_message: str
    ) -> tuple[str, bool]:
        """
        Handle Stage 3: Suggested Teammates
        Just guides conversation - frontend handles teammate selection
        Returns: (response_message, stage_completed)
        """
        system_prompt = """You are a friendly onboarding assistant helping users set up their workspace.

Current stage: Suggested Teammates

Your task is to introduce the teammate selection step and let the user know they can select teammates who will be helpful to them now or in the future. They can add or remove teammates later.

When the user indicates they understand or are ready to continue (says things like "got it", "continue", "next", "ready"), acknowledge and move to the next step.

Keep responses concise and friendly."""

        history = await self.get_conversation_history(state.conversation_id)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add initial message if first in stage
        if not history or history[-1].get("role") != "assistant" or "teammate" not in history[-1].get("content", "").lower():
            initial_message = "Great! Now let's set up your team. You can select teammates who will be helpful to you now or in the future. You can add or remove them later. Are you ready to select your teammates?"
            messages.append({"role": "assistant", "content": initial_message})
            await self.save_message(state.conversation_id, "assistant", initial_message, "suggested_teammates")
        
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        # Generate LLM response
        llm_response = await self.llm_service.generate(messages)

        # Check if user is ready to continue
        user_lower = user_message.lower()
        continue_keywords = ["ready", "continue", "next", "got it", "yes", "let's go", "sure"]
        
        if any(keyword in user_lower for keyword in continue_keywords):
            state.current_stage = "connect_world"
            response = "Perfect! Let's continue to connect your applications."
            await self.save_message(state.conversation_id, "assistant", response, "suggested_teammates")
            
            # Publish event for frontend
            channel = f"{self.settings.onboarding_channel_prefix}:{self.user.tenant_id}"
            await self.publisher.publish(
                channel,
                {
                    "type": "stage.completed",
                    "step": "suggested_teammates",
                    "next_step": "connect_world",
                    "tenant_id": self.user.tenant_id,
                    "conversation_id": state.conversation_id,
                },
            )
            return response, True

        await self.save_message(state.conversation_id, "assistant", llm_response, "suggested_teammates")
        return llm_response, False

    async def handle_connect_world(
        self, state: OnboardingState, user_message: str
    ) -> tuple[str, bool]:
        """
        Handle Stage 4: Connect Your World
        Just guides conversation - frontend handles integration connections
        Returns: (response_message, stage_completed)
        """
        system_prompt = """You are a friendly onboarding assistant helping users set up their workspace.

Current stage: Connect Your World

Your task is to introduce the integration connection step. Let the user know they can connect their applications so teammates can work seamlessly. They can connect or remove integrations later.

When the user indicates they understand or are ready (says things like "got it", "continue", "next", "skip", "later"), acknowledge and move to the next step.

Keep responses concise and friendly."""

        history = await self.get_conversation_history(state.conversation_id)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add initial message if first in stage
        if not history or history[-1].get("role") != "assistant" or "connect" not in history[-1].get("content", "").lower():
            initial_message = "Now let's connect your applications so your teammates can work seamlessly. You can connect or remove them later. Are you ready to connect your applications, or would you like to skip this step?"
            messages.append({"role": "assistant", "content": initial_message})
            await self.save_message(state.conversation_id, "assistant", initial_message, "connect_world")
        
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        # Generate LLM response
        llm_response = await self.llm_service.generate(messages)

        # Check if user wants to continue/skip
        user_lower = user_message.lower()
        continue_keywords = ["ready", "continue", "next", "got it", "yes", "let's go"]
        skip_keywords = ["skip", "later", "not now", "pass"]
        
        if any(keyword in user_lower for keyword in continue_keywords + skip_keywords):
            state.current_stage = "personalization"
            response = "No problem! You can connect your integrations later. Let's move on to personalizing your experience."
            await self.save_message(state.conversation_id, "assistant", response, "connect_world")
            
            # Publish event for frontend
            channel = f"{self.settings.onboarding_channel_prefix}:{self.user.tenant_id}"
            await self.publisher.publish(
                channel,
                {
                    "type": "stage.completed",
                    "step": "connect_world",
                    "next_step": "personalization",
                    "tenant_id": self.user.tenant_id,
                    "conversation_id": state.conversation_id,
                },
            )
            return response, True

        await self.save_message(state.conversation_id, "assistant", llm_response, "connect_world")
        return llm_response, False

    async def handle_personalization(
        self, state: OnboardingState, user_message: str
    ) -> tuple[str, bool]:
        """
        Handle Stage 5: Personalization
        Just guides conversation - frontend handles notification preferences
        Returns: (response_message, stage_completed)
        """
        system_prompt = """You are a friendly onboarding assistant helping users set up their workspace.

Current stage: Personalization

Your task is to introduce the notification preferences step. Let the user know they can select their preferred notification channels. This is the last step.

When the user indicates they understand or are ready (says things like "got it", "continue", "done", "ready"), acknowledge and complete onboarding.

Keep responses concise and friendly."""

        history = await self.get_conversation_history(state.conversation_id)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add initial message if first in stage
        if not history or history[-1].get("role") != "assistant" or "notification" not in history[-1].get("content", "").lower():
            initial_message = "Finally, let's set up your notification preferences. You can select your preferred notification channels. This is the last step! Are you ready to complete your onboarding?"
            messages.append({"role": "assistant", "content": initial_message})
            await self.save_message(state.conversation_id, "assistant", initial_message, "personalization")
        
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        # Generate LLM response
        llm_response = await self.llm_service.generate(messages)

        # Check if user is done
        user_lower = user_message.lower()
        done_keywords = ["done", "ready", "continue", "complete", "got it", "finished", "that's all"]
        
        if any(keyword in user_lower for keyword in done_keywords):
            state.current_stage = "completed"
            
            # Publish completion event
            channel = f"{self.settings.onboarding_channel_prefix}:{self.user.tenant_id}"
            await self.publisher.publish(
                channel,
                {
                    "type": "onboarding.completed",
                    "tenant_id": self.user.tenant_id,
                    "conversation_id": state.conversation_id,
                },
            )

            response = "Perfect! Your onboarding is complete. Welcome to Teems! Your workspace is now set up and ready to go."
            await self.save_message(state.conversation_id, "assistant", response, "personalization")
            return response, True

        await self.save_message(state.conversation_id, "assistant", llm_response, "personalization")
        return llm_response, False

