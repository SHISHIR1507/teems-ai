"""
Prompt Variator Tool for CrewAI
Generates 4 diverse prompt variants from a base intent and images
"""
import json
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import langsmith
from langsmith import traceable
from openai import OpenAI
from app.core.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL


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
        tags=["prompt-variation", "gpt-4o", "vision"],
        metadata={"model": "gpt-4o", "num_variants": 4}
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
        Generate 4 diverse prompt variants using GPT-4o with vision.
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
            name="initialize_gpt4o_client",
            tags=["llm-initialization"]
        ) as init_trace:
            client = OpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL
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
PROMPT STRUCTURE (MANDATORY - CRITICAL)
────────────────────────────────────────
Each prompt MUST start with identity-locking language to preserve the person's face.

REQUIRED FORMAT: "This exact person, [scene description]"

Examples:
- "This exact person, mid-shot in gym, holding product, facing camera directly"
- "This exact person, waist-up in modern office, presenting product naturally, body slightly angled"
- "This exact person, close-up in bright space, both hands on product, natural smile"

The phrase "This exact person" MUST be at the START of every prompt.
This signals to the image generation model that identity preservation is critical.

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
IDENTITY PRESERVATION (CRITICAL - HIGHEST PRIORITY)
────────────────────────────────────────
The person's IDENTITY must remain EXACTLY the same across all variants:
- Face structure, facial features, skin tone, eye color, nose shape, mouth shape
- Body type, height proportions, physical characteristics
- Hair color, hair style, hair texture
- Age appearance, facial expressions baseline
- ANY other identifying physical features

THESE MUST NEVER CHANGE. The person in the output must be recognizably the SAME person from the input image.

────────────────────────────────────────
PRODUCT CONSISTENCY
────────────────────────────────────────
- Preserve the product's exact appearance from the image
- Do NOT change product characteristics, colors, or design

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

This context must influence the prompts.
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
   - IMPORTANT: You may suggest different clothing styles to match the brand context
   - However, the person's IDENTITY (face, body type, skin tone, physical features) must remain EXACTLY the same
   - Only clothing, background, and environment should adapt to brand context

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
                    model=LLM_MODEL,
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
                                        "url": person_image_url,
                                        "detail": "low"
                                    }
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": product_image_url,
                                        "detail": "low"
                                    }
                                }
                            ]
                        }
                    ],
                    temperature=0.7,
                    timeout=60
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Received empty response from LLM")
                
                llm_trace.metadata.update({
                    "tokens_used": response.usage.total_tokens,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens
                })

                # Clean markdown blocks if present
                content_clean = content.strip()
                if content_clean.startswith("```"):
                    content_clean = content_clean.split("\n", 1)[1] if "\n" in content_clean else ""
                if content_clean.endswith("```"):
                    content_clean = content_clean[:-3].strip()
                elif content_clean.startswith("json"):  # Handle edge case
                    content_clean = content_clean[4:].strip()

                # Parse and validate JSON
                try:
                    variants_data = json.loads(content_clean)
                except json.JSONDecodeError:
                    # Fallback: try to find JSON object structure
                    import re
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        variants_data = json.loads(match.group(0))
                    else:
                        raise ValueError(f"Could not parse JSON from response: {content[:100]}...")

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
                import traceback
                traceback.print_exc()
                error_msg = f"Error generating prompt variants: {str(e)}"
                llm_trace.outputs = {"error": error_msg}
                
                # Fallback: generate simple variants without API
                print(f"API failed, using fallback prompts: {error_msg}")
                fallback_prompts = [
                    f"{base_intent}, mid-shot, holding product with right hand, facing camera directly",
                    f"{base_intent}, waist-up, holding product with left hand, body slightly angled",
                    f"{base_intent}, close framing, both hands on product, front view",
                    f"{base_intent}, mid-shot, one hand gesture, body at 45-degree angle"
                ]
                
                response_text = f"✅ TASK COMPLETE - 4 prompts generated successfully (fallback due to error: {str(e)}):\n\n"
                
                # Check if it was a BadRequest (likely image issue) and retry without images
                if "400" in str(e) or "invalid_image" in str(e):
                    print("Retrying prompt generation WITHOUT images...")
                    try:
                        # Retry with text only
                        response = client.chat.completions.create(
                            model=LLM_MODEL,
                            messages=[
                                {"role": "system", "content": system_instruction},
                                {
                                    "role": "user",
                                    "content": f"""{brand_context_block}Base intent: {base_intent}

Analyze the intent and brand context to generate 4 prompt variants."""
                                }
                            ],
                            temperature=0.7,
                            timeout=60
                        )
                        
                        content = response.choices[0].message.content
                        if content:
                            if content.startswith("```"):  # clean markdown again
                                content = content.split("\n", 1)[1] if "\n" in content else ""
                            if content.endswith("```"):
                                content = content[:-3].strip()
                            elif content.startswith("json"):
                                content = content[4:].strip()
                            
                            variants_data = json.loads(content)
                            prompts = variants_data.get("prompts", [])
                            if len(prompts) == 4:
                                response_text = "✅ TASK COMPLETE - 4 prompts generated successfully (text-only mode due to image error):\n\n"
                                fallback_prompts = prompts
                    except Exception as retry_e:
                        print(f"Retry failed: {str(retry_e)}")
                        # Use improved fallback prompts with brand context if retry fails
                        if fallback_prompts[0].startswith(f"{base_intent}, mid-shot"):  # if still default
                            fallback_prompts = [
                                f"{base_intent}, {industry} style, {vibe} vibe, mid-shot, holding product",
                                f"{base_intent}, appealing to {audience}, {vibe}, waist-up",
                                f"{base_intent}, {industry} aesthetic, close-up on product, {vibe}",
                                f"{base_intent}, UGC style for {audience}, {vibe}, dynamic angle"
                            ]
                
                for i, prompt in enumerate(fallback_prompts, 1):
                    response_text += f"Prompt {i}: {prompt}\n\n"
                
                response_text += "\n[PROMPT_GENERATION_COMPLETE] - Do not call this tool again."
                
                return response_text
