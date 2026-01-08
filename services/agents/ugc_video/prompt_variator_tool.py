"""
Prompt Variator Tool for CrewAI
Generates 4 diverse prompt variants from a base intent and images
"""
import os
import json
import base64
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import langsmith
from langsmith import traceable
from openai import OpenAI

class PromptVariatorInput(BaseModel):
    """Input schema for PromptVariatorTool."""
    base_intent: str = Field(..., description="Base user intent for generating diverse prompt variants")
    person_image_url: str = Field(..., description="S3 URL or HTTPS URL to the person image")
    product_image_url: str = Field(..., description="S3 URL or HTTPS URL to the product image")
    
    # Brand context (required, read-only)
    industry: str = Field(..., description="Brand industry context")
    audience: str = Field(..., description="Brand audience context")
    vibe: str = Field(..., description="Brand vibe context")

class PromptVariatorTool(BaseTool):
    name: str = "UGC Prompt Variator"
    description: str = """Generates 4 diverse prompt variants from person image URL, product image URL, and base intent. 
    Analyzes both images to create realistic UGC prompts that vary pose, hand usage, framing, and body orientation.
    Returns 4 prompts for image generation."""
    args_schema: Type[BaseModel] = PromptVariatorInput
    cache_function: bool = False

    @traceable(
        name="prompt_variator_tool",
        tags=["prompt-variation", "gpt-5.2", "vision"],
        metadata={"model": "gpt-5.2-2025-12-11", "num_variants": 4}
    )
    def _run(
        self, 
        base_intent: str, 
        person_image_url: str, 
        product_image_url: str,
        industry: str,
        audience: str,
        vibe: str
    ) -> str:
        """
        Generate 4 diverse prompt variants using GPT-5.2 with vision.
        Uses S3 URLs directly - no file I/O needed.
        """
        with langsmith.trace(
            name="validate_image_urls",
            tags=["validation", "s3-urls"]
        ) as validate_trace:
            if not person_image_url.startswith('http'):
                error_msg = f"Invalid person image URL: {person_image_url}"
                validate_trace.outputs = {"error": error_msg}
                return f"❌ Error: {error_msg}"
            
            if not product_image_url.startswith('http'):
                error_msg = f"Invalid product image URL: {product_image_url}"
                validate_trace.outputs = {"error": error_msg}
                return f"❌ Error: {error_msg}"
            
            validate_trace.outputs = {"status": "urls_validated", "uses_s3_urls": True}
            print(f"✅ Using S3 URLs directly (no file I/O needed)")

        with langsmith.trace(
            name="initialize_gpt52_client",
            tags=["llm-initialization"]
        ) as init_trace:
            client = OpenAI(
                api_key=os.getenv("AIML_API_KEY"),
                base_url="https://api.aimlapi.com/v1"
            )
            init_trace.outputs = {"client": "OpenAI"}

        system_instruction = """You are an Image-Aware UGC Prompt Maker.

You are given:
1) A person image
2) A product image  
3) A base user intent

Your task is to generate 4 concise, image-model-ready prompts for authentic, creator-style UGC imagery suitable for later lip-sync video.

You MUST base your prompts on what is actually visible in the images.
Do NOT assume features that are not clearly present.

────────────────────────────────────────
OUTPUT FORMAT (STRICT)
────────────────────────────────────────
Return STRICT JSON only:
{
  "prompts": [
    "prompt_variant_1",
    "prompt_variant_2",
    "prompt_variant_3",
    "prompt_variant_4"
  ]
}

────────────────────────────────────────
VARIATION GUIDELINES
────────────────────────────────────────
- Variant 1: Mid-shot, facing camera directly
- Variant 2: Waist-up, body slightly angled
- Variant 3: Closer framing, both hands involved naturally
- Variant 4: Mid-shot, body at ~45° angle with subtle gesture

────────────────────────────────────────
UGC REALISM (CRITICAL)
────────────────────────────────────────
- Image must feel candid, human, and creator-made
- Avoid staged, catalog, or advertisement-style posing
- Encourage relaxed posture, natural grip, slight asymmetry
- Product interaction should feel casual or mid-gesture
- Slight framing imperfection is preferred over rigid centering

────────────────────────────────────────
LIP-SYNC SAFETY (MANDATORY)
────────────────────────────────────────
- The mouth and lips must remain fully visible in all variants
- Hands or product must NOT cross or overlap the mouth region
- Natural hand motion is allowed as long as lips stay unobstructed
- Do NOT force rigid chest-level positioning

────────────────────────────────────────
PRODUCT TRUTH & LABEL HANDLING (VERY IMPORTANT)
────────────────────────────────────────
FIRST, visually inspect the product image and determine:
- Is there clearly visible printed text, branding, or labels on the product?

IF NO visible text or branding is clearly present:
- Treat the product as having NO labels
- Do NOT mention text, labels, barcodes, fine print, or blurring
- Do NOT invent compliance or hiding behavior

IF visible text or branding IS clearly present:
- Do NOT highlight or showcase it
- De-emphasize it naturally using:
  • casual grip
  • natural angle
  • depth of field
- Describe this subtly and visually
- NEVER use compliance language such as "hide", "obscure", "avoid", or "blur"

────────────────────────────────────────
CONSISTENCY RULES
────────────────────────────────────────
- Preserve the person's actual appearance from the image
- Preserve the product's actual appearance from the image
- Do NOT change identity, clothing, or product characteristics

────────────────────────────────────────
STYLE & LANGUAGE
────────────────────────────────────────
- Write in natural, visual, creator-style language
- No safety disclaimers, policy wording, or explanations
- No meta commentary about the images
- Focus on how the scene FEELS, not how it complies

────────────────────────────────────────
BRAND CONTEXT (LOCKED)
────────────────────────────────────────
You may receive brand context such as:
- Industry
- Audience
- Vibe

This context must  influence the prompts.
BRAND-DRIVEN VISUAL CONSISTENCY (MANDATORY):

The brand context MUST influence:

1. ENVIRONMENT & BACKGROUND:
   - Choose settings that feel native to the industry
   - Examples:
     • Fitness/wellness → gym, home workout space, outdoor trail
     • Tech/productivity → clean workspace, home office, minimal modern setting
     • Beauty/skincare → bathroom, vanity, natural light bedroom
     • Food/beverage → kitchen, cafe, casual dining space
   - Keep it simple and realistic (no elaborate sets)

2. CLOTHING & STYLING:
   - Dress the person appropriately for the audience and vibe
   - Examples:
     • Fitness brand → athletic wear, activewear, sporty casual
     • Tech brand → casual professional, hoodie, clean basics
     • Beauty brand → comfortable casual, cozy loungewear
   - Use what's visible in the person image as a BASE, but adjust if it doesn't match brand context

"""

        # Build brand context block (always present)
        brand_context_block = f"""Brand context (LOCKED):
Industry: {industry}
Audience: {audience}
Vibe: {vibe}

"""

        with langsmith.trace(
            name="call_gpt52_for_variants",
            inputs={
                "base_intent": base_intent, 
                "brand_context": {"industry": industry, "audience": audience, "vibe": vibe},
                "person_image_url": person_image_url,
                "product_image_url": product_image_url
            },
            tags=["llm-call", "vision", "s3-urls"]
        ) as llm_trace:
            try:
                response = client.chat.completions.create(
                    model="gpt-5.2-2025-12-11",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"""{brand_context_block}Base intent: {base_intent}

Analyze the person and product images and generate 4 prompt variants."""
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": person_image_url  # Use S3 URL directly
                                    }
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": product_image_url  # Use S3 URL directly
                                    }
                                }
                            ]
                        }
                    ],
                    temperature=0.7,
                    timeout=60
                )

                content = response.choices[0].message.content
                llm_trace.metadata.update({
                    "tokens_used": response.usage.total_tokens,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens
                })

                # Parse and validate JSON
                variants_data = json.loads(content)
                prompts = variants_data.get("prompts", [])

                if len(prompts) != 4:
                    raise ValueError(f"Expected 4 prompts, got {len(prompts)}")

                llm_trace.outputs = {"prompts": prompts}
                
                # Return structured response that clearly signals completion
                response_text = "✅ TASK COMPLETE - 4 prompts generated successfully:\n\n"
                
                for i, prompt in enumerate(prompts, 1):
                    response_text += f"Prompt {i}: {prompt}\n\n"
                
                response_text += "\n[PROMPT_GENERATION_COMPLETE] - Do not call this tool again."
                
                return response_text

            except Exception as e:
                error_msg = f"Error generating prompt variants: {str(e)[:200]}"
                llm_trace.outputs = {"error": error_msg}
                
                # Fallback: generate simple variants without API
                print(f"API failed, using fallback prompts: {error_msg}")
                fallback_prompts = [
                    f"{base_intent}, mid-shot, holding product with right hand, facing camera directly",
                    f"{base_intent}, waist-up, holding product with left hand, body slightly angled",
                    f"{base_intent}, close framing, both hands on product, front view",
                    f"{base_intent}, mid-shot, one hand gesture, body at 45-degree angle"
                ]
                
                response_text = "✅ TASK COMPLETE - 4 prompts generated successfully (fallback):\n\n"
                
                for i, prompt in enumerate(fallback_prompts, 1):
                    response_text += f"Prompt {i}: {prompt}\n\n"
                
                response_text += "\n[PROMPT_GENERATION_COMPLETE] - Do not call this tool again."
                
                return response_text
