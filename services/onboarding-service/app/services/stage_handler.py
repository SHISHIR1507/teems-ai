import re
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import Settings
from ..models import OnboardingState, ConversationMessage
from ..services.llm import LLMService
from ..services.clients import BrandfetchClient
from ..events import EventPublisher
from ..auth import AuthenticatedUser


class StageHandler:
    """Handles stage-specific logic for onboarding flow."""

    # Base system prompt with Eve's brand identity
    BASE_SYSTEM_PROMPT = """You are Eve — the Chief of Staff of the Teems.ai ecosystem.

Tone Guidelines:
- Calm and reassuring
- Friendly but not overly casual
- Smart, structured, and highly competent
- Professional and confident
- Clear and concise
- Non-intrusive and premium
- Never salesy, never overwhelming
- Never condescending

When responding:
- Be concise
- Be structured
- Guide the user smoothly
- Keep the user's mental effort at a minimum
- Make it feel like a natural conversation, not scripted or robotic
- Adapt your responses based on the conversation flow

Important: If the user asks questions or deviates from the onboarding flow, answer their question briefly and then gently guide them back to the current step. Be helpful but keep the onboarding moving forward."""

    # Expanded keywords for stage completion confirmation
    CONTINUE_KEYWORDS = [
        "ready", "continue", "next", "yes", "got it", "sure", "ok", "okay",
        "let's go", "proceed", "sounds good", "looks good", "correct",
        "that's good", "good to go", "all set", "all done", "done",
        "complete", "completed", "finished", "that's all", "that's it",
        "perfect", "great", "awesome", "excellent"
    ]
    
    # Additional keywords for skipping stages
    SKIP_KEYWORDS = ["skip", "later", "not now", "pass", "maybe later"]

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        llm_service: LLMService,
        brandfetch_client: BrandfetchClient,
        publisher: EventPublisher,
        user: AuthenticatedUser,
    ):
        self.session = session
        self.settings = settings
        self.llm_service = llm_service
        self.brandfetch_client = brandfetch_client
        self.publisher = publisher
        self.user = user

    @staticmethod
    def _extract_url_from_message(message: str) -> str | None:
        """Extract URL from user message that might contain extra text."""
        if not message or not message.strip():
            return None
        
        # Pattern to match URLs (http/https or domain patterns)
        # This pattern matches:
        # - http:// or https:// URLs
        # - Domain patterns like example.com, www.example.com, subdomain.example.com
        url_patterns = [
            r'https?://[^\s<>"\'\)]+',  # Full URLs with protocol
            r'(?:^|\s)(?:www\.)?[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+(?:[/?#][^\s<>"\'\)]*)?',  # Domain patterns
        ]
        
        for pattern in url_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                candidate = match.group(0).strip()
                # Clean up any trailing punctuation that's not part of URL
                candidate = candidate.rstrip('.,;:!?')
                # Basic validation - check if it looks like a domain/URL
                if candidate and (candidate.startswith(('http://', 'https://')) or '.' in candidate):
                    return candidate
        
        return None

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
        self, state: OnboardingState, user_message: str, auth_token: str | None = None
    ) -> tuple[str, bool]:
        """
        Handle Stage 2: Brand Discovery
        Returns: (response_message, stage_completed)
        """
        # Check if brandfetch has already been completed (waiting for user confirmation)
        if state.brand_domain:
            # Brandfetch completed, waiting for user confirmation
            system_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Brand Discovery (Confirmation)

The brand information has been fetched successfully. Use this tone and style as a guide, but make it conversational and natural:
"All set. Here's what I learned about your brand — feel free to adjust anything."

Your task is to confirm with the user that the brand data looks correct and ask if they're ready to continue. Be conversational, not scripted.

If the user asks unrelated questions or tries to deviate from the onboarding flow, answer briefly and then gently redirect them back to confirming the brand information and moving forward. Be helpful but keep the onboarding moving forward.

When the user indicates they're ready (says things like "yes", "continue", "next", "looks good", "ready"), acknowledge naturally and move to the next step."""

            history = await self.get_conversation_history(state.conversation_id)
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history[-10:])
            messages.append({"role": "user", "content": user_message})

            # Generate LLM response
            llm_response = await self.llm_service.generate(messages)

            # Check if user is ready to continue - expanded keywords
            user_lower = user_message.lower().strip()
            
            if any(keyword in user_lower for keyword in self.CONTINUE_KEYWORDS):
                # Save the LLM response first (even if we're transitioning)
                # This ensures conversation history is complete
                await self.save_message(state.conversation_id, "assistant", llm_response, "brand_discovery")
                
                state.current_stage = "suggested_teammates"
                await self.session.flush()  # Ensure state change is tracked
                
                # Get updated history including the just-saved message
                updated_history = await self.get_conversation_history(state.conversation_id)
                
                # Use LLM to generate transition message conversationally
                transition_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Suggested Teammates (Introduction)

You're transitioning to introduce the Teem Mates selection step. Use this tone and content as a guide, but make it conversational and natural:
"Great — I've got what I need. Here are a few high-impact Teem Mates that most businesses love to start with. Feel free to explore and test your Teem Mates. No credit card, no commitment - your workspace includes a free trial. If you're happy with them, you can upgrade anytime. They're versatile and work across almost every industry."

Generate a conversational introduction that captures the spirit of the example but feels natural and flows from the previous conversation."""

                transition_messages = [{"role": "system", "content": transition_prompt}]
                transition_messages.extend(updated_history[-5:])  # Use recent context including saved message
                transition_messages.append({"role": "user", "content": user_message})  # Use actual user message
                
                response = await self.llm_service.generate(transition_messages)
                await self.save_message(state.conversation_id, "assistant", response, "suggested_teammates")
                
                # Publish event for frontend
                channel = f"{self.settings.onboarding_channel_prefix}:{self.user.tenant_id}"
                await self.publisher.publish(
                    channel,
                    {
                        "type": "stage.completed",
                        "step": "brand_discovery",
                        "next_step": "suggested_teammates",
                        "tenant_id": self.user.tenant_id,
                        "conversation_id": state.conversation_id,
                    },
                )
                return response, True

            # Not ready - stage not completed
            await self.save_message(state.conversation_id, "assistant", llm_response, "brand_discovery")
            return llm_response, False

        # Brandfetch not yet completed - ask for URL
        system_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Brand Discovery

Your task is to guide the user through brand discovery. Use this tone and content as a guide for the first message, but make it conversational:
"Nice to meet you! Let's get your workspace ready — I'll guide everything for you.

To get your workspace set up, I'll take a quick look at your website and learn your brand's tone, style, and services.
What's your website?"

If this is the first message in the conversation, introduce yourself naturally and ask for their website in a conversational way.
Once they provide a valid website URL (like teems.ai), acknowledge it briefly.
If they provide an invalid URL or ask questions, politely guide them to provide a valid website URL.

If the user asks unrelated questions or tries to deviate from the onboarding flow, answer briefly and then gently redirect them back to providing their website URL. Be helpful but keep the onboarding moving forward."""

        # Get conversation history
        history = await self.get_conversation_history(state.conversation_id)
        is_first_message = not history or len([m for m in history if m.get("role") == "assistant"]) == 0
        
        # Extract URL from user message first to avoid unnecessary LLM call
        extracted_url = self._extract_url_from_message(user_message)
        
        # Only generate LLM response if no valid URL found
        if not extracted_url:
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history[-10:])
            messages.append({"role": "user", "content": user_message})

            # Generate LLM response (will generate initial message if needed, or respond conversationally)
            llm_response = await self.llm_service.generate(messages)
            
            # Save response (removed duplicate save logic)
            response = llm_response
            if "example" not in response.lower() and "teems.ai" not in response.lower():
                response += " For example, you could provide a URL like teems.ai"
            await self.save_message(state.conversation_id, "assistant", response, "brand_discovery")
            return response, False
        
        # Valid URL found - validate and proceed with brandfetch
        is_valid, error_msg = BrandfetchClient.validate_url(extracted_url)
        
        if not is_valid:
            # Invalid URL - generate LLM response to guide user
            # Get fresh history that includes the user's message
            updated_history = await self.get_conversation_history(state.conversation_id)
            
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(updated_history[-10:])  # Use updated history
            messages.append({"role": "user", "content": user_message})
            
            llm_response = await self.llm_service.generate(messages)
            
            # Save response (removed duplicate save logic)
            response = llm_response
            if "example" not in response.lower() and "teems.ai" not in response.lower():
                response += " For example, you could provide a URL like teems.ai"
            await self.save_message(state.conversation_id, "assistant", response, "brand_discovery")
            return response, False
        
        # Valid URL found - proceed with brandfetch
        # Extract domain from URL
        url_input = extracted_url.strip()
        if not url_input.startswith(("http://", "https://")):
            url_input = "https://" + url_input
        parsed = urlparse(url_input)
        domain = parsed.netloc or parsed.path.split("/")[0]
        if domain.startswith("www."):
            domain = domain[4:]

        # Call Brandfetch API - use url_input (normalized) not extracted_url (raw)
        try:
            brand_data = await self.brandfetch_client.fetch_brand(
                url_input,
                auth_token=auth_token,
            )
            
            # Update state with domain but DON'T change stage yet (wait for confirmation)
            state.brand_domain = domain
            await self.session.flush()  # CRITICAL: Flush state immediately so it's persisted
            
            # Publish event for frontend to display brand data
            channel = f"{self.settings.onboarding_channel_prefix}:{self.user.tenant_id}"
            await self.publisher.publish(
                channel,
                {
                    "type": "brandfetch.completed",
                    "step": "brand_discovery",
                    "tenant_id": self.user.tenant_id,
                    "conversation_id": state.conversation_id,
                    "domain": brand_data.get("domain"),
                    "name": brand_data.get("name"),
                },
            )

            # Get fresh history that includes the user's message
            updated_history = await self.get_conversation_history(state.conversation_id)
            
            # Use LLM to generate a conversational response about the fetched brand
            # If first message, include greeting; otherwise just acknowledge
            if is_first_message:
                success_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Brand Discovery

This is the first message in the conversation. The user provided their website URL ({extracted_url}) right away.

You've successfully fetched the brand information for {domain}. Use this tone as a guide, but make it conversational and natural:
"Nice to meet you! I've fetched your brand information for {domain}. Here's what I learned — feel free to adjust anything."

Generate a natural, conversational response that both greets the user and confirms you've fetched the brand information. Keep it brief, friendly, and welcoming."""
            else:
                success_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Brand Discovery

You've successfully fetched the brand information for {domain}. Use this tone as a guide, but make it conversational and natural:
"All set. Here's what I learned about your brand — feel free to adjust anything."

Generate a natural, conversational response confirming that you've fetched the brand information. Keep it brief, friendly, and match the user's energy from the conversation."""

            success_messages = [{"role": "system", "content": success_prompt}]
            success_messages.extend(updated_history[-5:])  # Use updated history
            success_messages.append({"role": "user", "content": user_message})  # Use actual user message
            
            response = await self.llm_service.generate(success_messages)
            await self.save_message(state.conversation_id, "assistant", response, "brand_discovery")
            return response, False  # Stage not completed yet - waiting for confirmation
        except HTTPException as e:
            # Handle HTTP exceptions gracefully - log and use LLM for conversational response
            logger.error(
                f"Brandfetch API error for URL {url_input}: {e.status_code} - {e.detail}",
                exc_info=True
            )
            
            # Get fresh history that includes the user's message
            updated_history = await self.get_conversation_history(state.conversation_id)
            
            # Determine error context for better LLM response
            error_context = ""
            if e.status_code == 404:
                error_context = f"The brand information for '{domain}' is not available in Brandfetch's database. This domain might not be in their system yet."
            elif e.status_code == 422:
                error_context = f"Brandfetch rejected the domain '{domain}' as invalid."
            elif e.status_code == 400:
                error_context = f"The URL was invalid: {e.detail}"
            elif e.status_code == 429:
                error_context = "Brandfetch rate limit exceeded. Please try again in a moment."
            else:
                error_context = f"An error occurred while fetching brand information: {e.detail}"
            
            # Use LLM to generate a conversational error response
            error_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Brand Discovery

The user provided a URL ({extracted_url}), but there was an issue fetching the brand information. {error_context}

Use this tone as a guide, but make it conversational and helpful:
"Please check your url again."

Generate a natural, conversational response that acknowledges the issue and gently asks the user to check their URL or try a different one. Be helpful and not frustrating. Keep it brief."""

            error_messages = [{"role": "system", "content": error_prompt}]
            error_messages.extend(updated_history[-5:])  # Use updated history
            error_messages.append({"role": "user", "content": user_message})
            
            error_response = await self.llm_service.generate(error_messages)
            await self.save_message(state.conversation_id, "assistant", error_response, "brand_discovery")
            return error_response, False
        except Exception as e:
            # Log the actual error for debugging
            logger.error(
                f"Error fetching brand information for URL {extracted_url}: {type(e).__name__}: {e}",
                exc_info=True
            )
            
            # Get fresh history that includes the user's message
            updated_history = await self.get_conversation_history(state.conversation_id)
            
            # Use LLM to generate a conversational error response
            error_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Brand Discovery

The user provided a URL ({extracted_url}), but there was an unexpected error fetching the brand information.

Use this tone as a guide, but make it conversational and helpful:
"Please check your url again."

Generate a natural, conversational response that acknowledges the issue and gently asks the user to check their URL or try again. Be helpful and not frustrating. Keep it brief."""

            error_messages = [{"role": "system", "content": error_prompt}]
            error_messages.extend(updated_history[-5:])  # Use updated history
            error_messages.append({"role": "user", "content": user_message})
            
            error_response = await self.llm_service.generate(error_messages)
            await self.save_message(state.conversation_id, "assistant", error_response, "brand_discovery")
            return error_response, False

    async def handle_suggested_teammates(
        self, state: OnboardingState, user_message: str
    ) -> tuple[str, bool]:
        """
        Handle Stage 3: Suggested Teammates
        Just guides conversation - frontend handles teammate selection
        Returns: (response_message, stage_completed)
        """
        system_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Suggested Teammates

Your task is to introduce the Teem Mates selection step. Use this tone and content as a guide, but make it conversational:
"Great — I've got what I need. Here are a few high-impact Teem Mates that most businesses love to start with. Feel free to explore and test your Teem Mates. No credit card, no commitment - your workspace includes a free trial. If you're happy with them, you can upgrade anytime. They're versatile and work across almost every industry."

Let the user know they can select teammates who will be helpful to them now or in the future. They can add or remove teammates later.
Be conversational and adapt to the user's responses.

If the user asks unrelated questions or tries to deviate from the onboarding flow, answer briefly and then gently redirect them back to the teammate selection step. Be helpful but keep the onboarding moving forward.

When the user indicates they understand or are ready to continue (says things like "got it", "continue", "next", "ready"), acknowledge naturally and move to the next step."""

        history = await self.get_conversation_history(state.conversation_id)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Check if this is the first message in this stage by checking message stage field
        is_first_in_stage = True
        if history:
            # Get last assistant message and check its stage
            stmt = (
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == state.conversation_id,
                    ConversationMessage.role == "assistant"
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            last_msg = result.scalar_one_or_none()
            
            if last_msg and last_msg.stage == "suggested_teammates":
                is_first_in_stage = False
        
        # If first message in stage, LLM will generate the initial introduction
        # Otherwise, it will respond to the user's message conversationally
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        # Generate LLM response
        llm_response = await self.llm_service.generate(messages)

        # Check if user is ready to continue - expanded keywords
        user_lower = user_message.lower().strip()
        
        if any(keyword in user_lower for keyword in self.CONTINUE_KEYWORDS):
            # Save the LLM response first (even if we're transitioning)
            # This ensures conversation history is complete
            await self.save_message(state.conversation_id, "assistant", llm_response, "suggested_teammates")
            
            state.current_stage = "connect_world"
            await self.session.flush()  # Ensure state change is tracked
            
            # Get updated history including the just-saved message
            updated_history = await self.get_conversation_history(state.conversation_id)
            
            # Use LLM to generate transition message conversationally
            transition_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Connect Your World (Introduction)

You're transitioning to introduce the integration connection step. Use this tone and content as a guide, but make it conversational:
"If you already use any of these tools, I can connect them now so your Teem Mates can start working instantly. Totally optional — you can skip for now."

Generate a conversational introduction that captures the spirit of the example but feels natural and flows from the previous conversation."""

            transition_messages = [{"role": "system", "content": transition_prompt}]
            transition_messages.extend(updated_history[-5:])  # Use recent context including saved message
            transition_messages.append({"role": "user", "content": user_message})  # Use actual user message
            
            response = await self.llm_service.generate(transition_messages)
            await self.save_message(state.conversation_id, "assistant", response, "connect_world")
            
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

        # Not ready - stage not completed, save the response
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
        system_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Connect Your World

Your task is to introduce the integration connection step. Use this tone and content as a guide, but make it conversational:
"If you already use any of these tools, I can connect them now so your Teem Mates can start working instantly. Totally optional — you can skip for now."

Let the user know they can connect their applications so teammates can work seamlessly. They can connect or remove integrations later.
Be conversational and adapt to whether the user wants to connect or skip.

If the user asks unrelated questions or tries to deviate from the onboarding flow, answer briefly and then gently redirect them back to the integration connection step. Be helpful but keep the onboarding moving forward.

When the user indicates they understand or are ready (says things like "got it", "continue", "next", "skip", "later"), acknowledge naturally and move to the next step."""

        history = await self.get_conversation_history(state.conversation_id)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Check if this is the first message in this stage by checking message stage field
        is_first_in_stage = True
        if history:
            # Get last assistant message and check its stage
            stmt = (
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == state.conversation_id,
                    ConversationMessage.role == "assistant"
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            last_msg = result.scalar_one_or_none()
            
            if last_msg and last_msg.stage == "connect_world":
                is_first_in_stage = False
        
        # If first message in stage, LLM will generate the initial introduction
        # Otherwise, it will respond to the user's message conversationally
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        # Generate LLM response
        llm_response = await self.llm_service.generate(messages)

        # Check if user wants to continue/skip - expanded keywords
        user_lower = user_message.lower().strip()
        
        if any(keyword in user_lower for keyword in self.CONTINUE_KEYWORDS + self.SKIP_KEYWORDS):
            # Save the LLM response first (even if we're transitioning)
            # This ensures conversation history is complete
            await self.save_message(state.conversation_id, "assistant", llm_response, "connect_world")
            
            state.current_stage = "personalization"
            await self.session.flush()  # Ensure state change is tracked
            
            # Get updated history including the just-saved message
            updated_history = await self.get_conversation_history(state.conversation_id)
            
            # Use LLM to generate transition message conversationally
            transition_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Personalization (Introduction)

You're transitioning to introduce the notification preferences step. This is the last step. Use this tone and content as a guide, but make it conversational:
"Almost done! How often would you like me to update you about your Teem Mates' activity?

And where should I deliver your updates?"

Generate a conversational introduction that captures the spirit of the example but feels natural and flows from the previous conversation."""

            transition_messages = [{"role": "system", "content": transition_prompt}]
            transition_messages.extend(updated_history[-5:])  # Use recent context including saved message
            transition_messages.append({"role": "user", "content": user_message})  # Use actual user message
            
            response = await self.llm_service.generate(transition_messages)
            await self.save_message(state.conversation_id, "assistant", response, "personalization")
            
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

        # Not ready - stage not completed, save the response
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
        system_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Personalization

Your task is to introduce the notification preferences step. This is the last step before onboarding is complete. Use this tone and content as a guide, but make it conversational:
"Almost done! How often would you like me to update you about your Teem Mates' activity?

And where should I deliver your updates?"

Let the user know they can select their preferred notification channels. Be conversational and encouraging.

If the user asks unrelated questions or tries to deviate from the onboarding flow, answer briefly and then gently redirect them back to the notification preferences step. Be helpful but keep the onboarding moving forward - we're almost done!

When the user indicates they understand or are ready (says things like "got it", "continue", "done", "ready"), acknowledge naturally and complete onboarding."""

        history = await self.get_conversation_history(state.conversation_id)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Check if this is the first message in this stage by checking message stage field
        is_first_in_stage = True
        if history:
            # Get last assistant message and check its stage
            stmt = (
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == state.conversation_id,
                    ConversationMessage.role == "assistant"
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            last_msg = result.scalar_one_or_none()
            
            if last_msg and last_msg.stage == "personalization":
                is_first_in_stage = False
        
        # If first message in stage, LLM will generate the initial introduction
        # Otherwise, it will respond to the user's message conversationally
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        # Generate LLM response
        llm_response = await self.llm_service.generate(messages)

        # Check if user is done - using expanded keywords
        user_lower = user_message.lower().strip()
        
        if any(keyword in user_lower for keyword in self.CONTINUE_KEYWORDS):
            # Save the LLM response first (even if we're completing)
            # This ensures conversation history is complete
            await self.save_message(state.conversation_id, "assistant", llm_response, "personalization")
            
            state.current_stage = "completed"
            await self.session.flush()  # Ensure state change is tracked
            
            # Get updated history including the just-saved message
            updated_history = await self.get_conversation_history(state.conversation_id)
            
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

            # Use LLM to generate completion message conversationally
            completion_prompt = f"""{self.BASE_SYSTEM_PROMPT}

Current stage: Onboarding Complete

The onboarding is now complete! Use this tone and content as a guide, but make it conversational and celebratory:
"Your workspace is ready! Your Teem Mates are set — and I'll keep everything organized for you. Now, onboard your teem mates and get them to work. Remember I'm always a chat away incase you need any help."

Generate a conversational, friendly completion message that celebrates the milestone and makes the user feel supported. Make it natural and match the conversation's energy."""

            completion_messages = [{"role": "system", "content": completion_prompt}]
            completion_messages.extend(updated_history[-5:])  # Use recent context including saved message
            completion_messages.append({"role": "user", "content": user_message})  # Use actual user message
            
            response = await self.llm_service.generate(completion_messages)
            await self.save_message(state.conversation_id, "assistant", response, "personalization")
            return response, True

        # Not done - stage not completed, save the response
        await self.save_message(state.conversation_id, "assistant", llm_response, "personalization")
        return llm_response, False

