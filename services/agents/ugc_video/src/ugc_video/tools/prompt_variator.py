"""
Prompt Variator Tool for CrewAI
Generates 4 diverse prompt variants from a base intent
"""
import os
import json
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import langsmith
from langsmith import traceable
from openai import OpenAI

from ..config import get_settings


class PromptVariatorInput(BaseModel):
    """Input schema for PromptVariatorTool."""
    base_intent: str = Field(..., description="Base user intent for generating diverse prompt variants")


class PromptVariatorTool(BaseTool):
    name: str = "UGC Prompt Variator"
    description: str = """Generates 4 diverse prompt variants from a base user intent. 
    Each variant preserves identity and intent but varies pose, hand usage, framing, and body orientation.
    Returns a JSON string with 4 prompts that you can use for image generation."""
    args_schema: Type[BaseModel] = PromptVariatorInput
    cache_function: bool = False

    @traceable(
        name="prompt_variator_tool",
        tags=["prompt-variation", "gpt-5"],
        metadata={"model": "gpt-5-2025-08-07", "num_variants": 4}
    )
    def _run(self, base_intent: str) -> str:
        """
        Generate 4 diverse prompt variants using GPT-5.
        """
        settings = get_settings()
        
        with langsmith.trace(
            name="initialize_gpt5_client",
            tags=["llm-initialization"]
        ) as init_trace:
            client = OpenAI(
                api_key=settings.aiml_api_key,
                base_url=settings.aiml_base_url
            )
            init_trace.outputs = {"client": "OpenAI"}

        system_instruction = """You are a UGC Prompt Variator. Given a base user intent, generate 4 concise, image-model-ready prompts that preserve identity and intent but vary pose, hand usage, framing, and body orientation. Do not change clothing, environment, lighting, or facial expression.

Output STRICT JSON format:
{"prompts": ["prompt_variant_1", "prompt_variant_2", "prompt_variant_3", "prompt_variant_4"]}

Variation guidelines:
- Variant 1: Mid-shot, holding product with right hand, facing camera directly
- Variant 2: Waist-up, holding product with left hand, body slightly angled
- Variant 3: Close framing, both hands on product, front view
- Variant 4: Mid-shot, one hand gesture, body at 45-degree angle"""

        with langsmith.trace(
            name="call_gpt5_for_variants",
            inputs={"base_intent": base_intent},
            tags=["llm-call"]
        ) as llm_trace:
            try:
                response = client.chat.completions.create(
                    model="openai/gpt-5-2025-08-07",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": f"Base intent: {base_intent}\n\nGenerate 4 prompt variants."}
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

