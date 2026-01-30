"""
Brand Sync Tool for CrewAI
Allows conversational brand context setting and updates
"""

from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio


class BrandSyncInput(BaseModel):
    """Input schema for Brand Sync Tool."""
    industry: str = Field(
        ...,
        description="Brand industry (e.g., fitness, beauty, tech, food, fashion)"
    )
    audience: str = Field(
        ...,
        description="Target audience (e.g., millennials, Gen Z, professionals, parents)"
    )
    vibe: str = Field(
        ...,
        description="Brand vibe/tone (e.g., energetic, calm, professional, playful, authentic)"
    )
    product_name: str = Field(
        ...,
        description="Product name (e.g., 'Glow Serum', 'Energy Drink', 'Fitness App')"
    )
    conversation_id: str = Field(
        default=None,
        description="Conversation ID to associate brand context with (auto-filled if not provided)"
    )
    tenant_id: str = Field(
        default=None,
        description="Tenant ID for multi-tenant isolation (auto-filled if not provided)"
    )


class BrandSyncTool(BaseTool):
    name: str = "Brand Sync"
    description: str = (
        "Syncs and locks brand context (industry, audience, vibe, product_name) for a conversation. "
        "Use this when the user provides their brand information conversationally. "
        "Once synced, the brand context is locked and used for all UGC generation in this conversation."
    )
    args_schema: Type[BaseModel] = BrandSyncInput
    cache_function: bool = False
    
    # Store context as class attributes (will be set when tool is instantiated)
    _conversation_id: str = None
    _tenant_id: str = None
    
    def _run(
        self,
        industry: str,
        audience: str,
        vibe: str,
        product_name: str,
        conversation_id: str = None,
        tenant_id: str = None
    ) -> str:
        """
        Sync brand context to database.
        
        Args:
            industry: Brand industry
            audience: Target audience
            vibe: Brand vibe/tone
            product_name: Product name
            conversation_id: Conversation ID (optional, uses stored value if not provided)
            tenant_id: Tenant ID (optional, uses stored value if not provided)
            
        Returns:
            Confirmation message with brand context
        """
        # Use stored context if not provided
        if not conversation_id:
            conversation_id = self._conversation_id
        if not tenant_id:
            tenant_id = self._tenant_id
            
        if not conversation_id or not tenant_id:
            return "Error: conversation_id and tenant_id are required for brand sync"
        
        try:
            # Import here to avoid circular dependencies
            from app.services import db_helpers
            from app.core.database import init_engine, async_session_maker
            
            # Initialize engine if not already done
            init_engine()
            
            # Try to get the running loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No loop running, create one
                loop = None
            
            if loop and loop.is_running():
                # We're in a running loop - use nest_asyncio to allow nested calls
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                    result = asyncio.run(self._sync_brand_async(
                        industry, audience, vibe, product_name, conversation_id, tenant_id
                    ))
                    return result
                except ImportError:
                    # nest_asyncio not available, return error message
                    return "Error: Cannot sync brand in async context. Please install nest-asyncio: pip install nest-asyncio"
            else:
                # No running loop, safe to use asyncio.run()
                result = asyncio.run(self._sync_brand_async(
                    industry, audience, vibe, product_name, conversation_id, tenant_id
                ))
                return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error syncing brand context: {str(e)}"
    
    async def _sync_brand_async(
        self,
        industry: str,
        audience: str,
        vibe: str,
        product_name: str,
        conversation_id: str,
        tenant_id: str
    ) -> str:
        """Async helper to sync brand context."""
        from app.services import db_helpers
        from app.core.database import async_session_maker
        
        async with async_session_maker() as session:
            # Get or create conversation
            conversation = await db_helpers.get_conversation(
                session, conversation_id, tenant_id
            )
            
            was_already_synced = False
            
            if not conversation:
                # Create new conversation with brand context
                conversation = await db_helpers.create_conversation(
                    session,
                    conversation_id,
                    tenant_id,
                    user_id=None,
                    brand_industry=industry,
                    brand_audience=audience,
                    brand_vibe=vibe,
                    brand_locked=True
                )
                # Update product name
                await db_helpers.update_product_name(session, conversation_id, tenant_id, product_name)
            else:
                # Update existing conversation
                was_already_synced = conversation.brand_locked if hasattr(conversation, 'brand_locked') else False
                
                conversation = await db_helpers.update_conversation_brand(
                    session,
                    conversation_id,
                    tenant_id,
                    industry,
                    audience,
                    vibe
                )
                # Update product name
                await db_helpers.update_product_name(session, conversation_id, tenant_id, product_name)
            
            # Add system message
            await db_helpers.add_message(
                session,
                conversation_id,
                tenant_id,
                "system",
                f"Brand sync: {industry} | {audience} | {vibe} | Product: {product_name}"
            )
            
            # Commit the transaction
            await session.commit()
            
            # Return confirmation
            action = "updated" if was_already_synced else "synced"
            return f"""✅ Brand context {action} successfully!

Industry: {industry}
Audience: {audience}
Vibe: {vibe}
Product: {product_name}

This brand context is now locked for this conversation and will be used for all UGC generation."""
