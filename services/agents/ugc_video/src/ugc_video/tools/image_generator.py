"""
Banana UGC Image Generator Tool for CrewAI
Generates UGC-style images using google/nano-banana-pro-edit model
Supports Physical Product, Digital Product, and Service types
"""
import base64
import os
import requests
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import langsmith
from langsmith import traceable

from ..config import get_settings
from ..models.conversation import UGCType


class BananaUGCInput(BaseModel):
    """Input schema for BananaUGCTool."""
    person_image_path: str = Field(..., description="Path to the person image file")
    product_image_path: str = Field(None, description="Path to the product image file (optional for service type)")
    screenshot_path: str = Field(None, description="Path to screenshot file (for digital product type)")
    logo_path: str = Field(None, description="Path to logo file (for service type)")
    prompt: str = Field(
        default="A person showcasing a product in a natural, engaging way",
        description="Description of how the person should showcase the product"
    )
    output_filename: str = Field(
        default="generated_ugc_image.png",
        description="Output filename for the generated image"
    )
    ugc_type: str = Field(
        default="physical_product",
        description="Type of UGC: physical_product, digital_product, or service"
    )


class BananaUGCTool(BaseTool):
    name: str = "Banana UGC Image Generator"
    description: str = "Generates a UGC-style image where a person is showcasing a product using AI/ML API"
    args_schema: Type[BaseModel] = BananaUGCInput

    @traceable(
        name="banana_ugc_tool",
        tags=["image-generation", "banana-api", "ugc"],
        metadata={"model": "google/nano-banana-pro-edit", "provider": "aiml-api"}
    )
    def _run(
        self,
        person_image_path: str,
        product_image_path: str | None = None,
        screenshot_path: str | None = None,
        logo_path: str | None = None,
        prompt: str = "A person showcasing a product in a natural, engaging way",
        output_filename: str = "generated_ugc_image.png",
        ugc_type: str = "physical_product"
    ) -> str:
        """
        Generate UGC image using AI/ML API with google/nano-banana-pro model.
        Supports three types: physical_product, digital_product, service
        """
        settings = get_settings()
        
        if not settings.aiml_api_key:
            return "Error: AIML_API_KEY not found in environment variables"

        # Read and encode images with tracing
        with langsmith.trace(
            name="encode_input_images",
            inputs={
                "person_image_path": person_image_path,
                "product_image_path": product_image_path,
                "screenshot_path": screenshot_path,
                "logo_path": logo_path,
                "ugc_type": ugc_type
            },
            tags=["image-processing", "base64-encoding"],
            metadata={}
        ) as encode_trace:
            try:
                with open(person_image_path, "rb") as f:
                    person_image_data = f.read()
                    person_image_b64 = base64.b64encode(person_image_data).decode()

                image_urls = [f"data:image/jpeg;base64,{person_image_b64}"]
                
                # Handle different UGC types
                if ugc_type == UGCType.PHYSICAL_PRODUCT.value:
                    if not product_image_path:
                        return "Error: product_image_path required for physical_product type"
                    with open(product_image_path, "rb") as f:
                        product_image_data = f.read()
                        product_image_b64 = base64.b64encode(product_image_data).decode()
                    image_urls.append(f"data:image/jpeg;base64,{product_image_b64}")
                    full_prompt = (
                        f"Combine these images to create a realistic UGC-style photo where the person "
                        f"from the first image is naturally showcasing the product from the second image. "
                        f"{prompt}. Keep the same person's face and identity, and the exact product appearance. "
                        f"Make it look like authentic user-generated content."
                    )
                elif ugc_type == UGCType.DIGITAL_PRODUCT.value:
                    if screenshot_path:
                        with open(screenshot_path, "rb") as f:
                            screenshot_data = f.read()
                            screenshot_b64 = base64.b64encode(screenshot_data).decode()
                        image_urls.append(f"data:image/jpeg;base64,{screenshot_b64}")
                    full_prompt = (
                        f"Create a realistic UGC-style photo where the person from the first image is "
                        f"holding or displaying a device (laptop, tablet, or phone) showing the digital product "
                        f"from the second image. {prompt}. The device should be naturally integrated into the scene. "
                        f"Keep the same person's face and identity. Make it look like authentic user-generated content."
                    )
                elif ugc_type == UGCType.SERVICE.value:
                    if logo_path:
                        with open(logo_path, "rb") as f:
                            logo_data = f.read()
                            logo_b64 = base64.b64encode(logo_data).decode()
                        image_urls.append(f"data:image/jpeg;base64,{logo_b64}")
                    full_prompt = (
                        f"Create a realistic UGC-style photo where the person from the first image is "
                        f"talking about or presenting a service. {prompt}. "
                        f"If a logo is provided, naturally incorporate it into the scene (e.g., on a background, "
                        f"on a device screen, or as a subtle watermark). Keep the same person's face and identity. "
                        f"Make it look like authentic user-generated content."
                    )
                else:
                    return f"Error: Unknown UGC type: {ugc_type}"

                encode_trace.metadata.update({
                    "person_image_size": len(person_image_data),
                    "num_images": len(image_urls),
                    "ugc_type": ugc_type
                })
                encode_trace.outputs = {"status": "images_encoded"}

            except FileNotFoundError as e:
                error_msg = f"Error: Image file not found - {str(e)}"
                encode_trace.outputs = {"error": error_msg}
                return error_msg

        # AI/ML API endpoint
        url = f"{settings.aiml_base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {settings.aiml_api_key}",
            "Content-Type": "application/json"
        }

        # Use correct schema for google/nano-banana-pro-edit
        payload = {
            "model": "google/nano-banana-pro-edit",
            "prompt": full_prompt,
            "image_urls": image_urls,
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "num_images": 1
        }

        # Call image generation API with detailed tracing
        with langsmith.trace(
            name="call_banana_api",
            inputs={
                "model": "google/nano-banana-pro-edit",
                "prompt": full_prompt,
                "num_images": 1,
                "ugc_type": ugc_type
            },
            tags=["api-call", "image-generation", "aiml-api"],
            metadata={
                "provider": "AI/ML API",
                "endpoint": url,
                "model": "google/nano-banana-pro-edit"
            }
        ) as api_trace:
            try:
                import time
                start_time = time.time()

                print(f"\n🎨 Calling Banana API for {output_filename}...")
                print(f"   Model: {payload['model']}")
                print(f"   Type: {ugc_type}")
                print(f"   Prompt: {full_prompt[:100]}...")
                
                response = requests.post(url, json=payload, headers=headers, timeout=180)

                latency = time.time() - start_time

                # Log API call metadata
                api_trace.metadata.update({
                    "status_code": response.status_code,
                    "latency_seconds": round(latency, 2),
                    "response_size_bytes": len(response.content)
                })

                # Accept both 200 and 201 status codes
                if response.status_code not in [200, 201]:
                    error_msg = f"Error: API returned status {response.status_code}: {response.text[:500]}"
                    api_trace.outputs = {"error": error_msg, "status_code": response.status_code}
                    print(f"❌ API Error: {error_msg}")
                    return error_msg

                result = response.json()
                print(f"✅ API Success! Status: {response.status_code}")
                api_trace.outputs = {"status": "success", "result_keys": list(result.keys())}

            except requests.exceptions.Timeout:
                error_msg = f"Error: API request timed out after 180 seconds"
                api_trace.outputs = {"error": error_msg}
                print(error_msg)
                return error_msg
            except requests.exceptions.RequestException as e:
                error_msg = f"Error calling AI/ML API: {str(e)[:200]}"
                api_trace.outputs = {"error": error_msg}
                print(error_msg)
                return error_msg

        # Save the generated image with tracing
        with langsmith.trace(
            name="save_generated_image",
            tags=["image-output", "file-save"],
            metadata={}
        ) as save_trace:
            if "data" in result and len(result["data"]) > 0:
                image_data = result["data"][0]
                output_path = output_filename

                # Check if it's a URL or base64
                if "url" in image_data:
                    # Download from URL
                    img_response = requests.get(image_data["url"])
                    img_response.raise_for_status()

                    with open(output_path, "wb") as f:
                        f.write(img_response.content)

                    save_trace.metadata.update({
                        "method": "url_download",
                        "image_url": image_data["url"],
                        "output_path": output_path,
                        "image_size_bytes": len(img_response.content)
                    })
                    save_trace.outputs = {"output_path": output_path, "url": image_data["url"]}

                    return f"✅ SUCCESS: Image saved to {output_path}"

                elif "b64_json" in image_data:
                    # Decode base64
                    image_bytes = base64.b64decode(image_data["b64_json"])

                    with open(output_path, "wb") as f:
                        f.write(image_bytes)

                    save_trace.metadata.update({
                        "method": "base64_decode",
                        "output_path": output_path,
                        "image_size_bytes": len(image_bytes)
                    })
                    save_trace.outputs = {"output_path": output_path}

                    return f"✅ SUCCESS: Image saved to {output_path}"

                else:
                    error_msg = f"Error: Unexpected image format in response - {result}"
                    save_trace.outputs = {"error": error_msg}
                    return error_msg
            else:
                error_msg = f"Error: No image data in response - {result}"
                save_trace.outputs = {"error": error_msg}
                return error_msg

