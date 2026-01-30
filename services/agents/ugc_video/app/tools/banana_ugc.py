import requests
import base64
from crewai.tools import BaseTool
from typing import Type, List, Optional
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
from io import BytesIO
from google import genai
from PIL import Image
from app.core.config import GEMINI_API_KEY, S3_FOLDER_PREFIX
from app.services.s3_utils import upload_bytes_to_s3


class BananaUGCInput(BaseModel):
    """Input schema for BananaUGCTool."""
    person_image_url: str = Field(..., description="S3 URL or HTTPS URL to the person image")
    product_image_url: str = Field(..., description="S3 URL or HTTPS URL to the product image")
    prompts: List[str] = Field(
        ...,
        description="List of 4 prompt variants for parallel image generation"
    )
    conversation_id: Optional[str] = Field(None, description="Conversation ID for S3 organization")
    upload_to_s3: bool = Field(default=False, description="Whether to upload generated images to S3")


class BananaUGCTool(BaseTool):
    name: str = "Banana UGC Image Generator"
    description: str = "Generates 4 UGC-style images in parallel where a person is showcasing a product. Takes S3 URLs and a list of 4 prompts, generates all images concurrently using Google Gemini."
    args_schema: Type[BaseModel] = BananaUGCInput

    def _run(
        self,
        person_image_url: str,
        product_image_url: str,
        prompts: List[str],
        conversation_id: Optional[str] = None,
        upload_to_s3: bool = False
    ) -> str:
        """
        Generate 4 UGC images in parallel using Google Gemini API.
        Optimized: reuse client, 1K resolution, batch S3 upload.
        """
        if len(prompts) != 4:
            return f"Error: Expected exactly 4 prompts, got {len(prompts)}"

        if not GEMINI_API_KEY:
            return "Error: GEMINI_API_KEY not found in environment variables"

        # Validate and download images once
        if not person_image_url.startswith('http') or not product_image_url.startswith('http'):
            return f"Error: Invalid image URLs"

        print(f"✅ Downloading images from S3...")
        try:
            person_img = self._download_image(person_image_url)
            product_img = self._download_image(product_image_url)
        except Exception as e:
            return f"Error downloading images: {str(e)}"

        # Create Gemini client once (optimization #1)
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Generate images in parallel (without S3 upload)
        print(f"\n🚀 Starting parallel generation of 4 images with Gemini...")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for idx, prompt in enumerate(prompts, 1):
                future = executor.submit(
                    self._generate_single_image,
                    client,  # Pass shared client
                    person_img,
                    product_img,
                    prompt,
                    idx
                )
                futures[future] = idx

            # Collect results (image bytes only, no S3 upload yet)
            results = {}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    results[idx] = result
                    print(f"✅ Image {idx}/4 generated")
                except Exception as e:
                    results[idx] = {"success": False, "error": str(e)}
                    print(f"❌ Image {idx}/4 failed: {str(e)}")

        gen_time = time.time() - start_time
        print(f"⚡ Generation completed in {gen_time:.2f}s")

        # Batch upload to S3 (optimization #4)
        if upload_to_s3 and conversation_id:
            print(f"☁️ Uploading {len([r for r in results.values() if r.get('success')])} images to S3...")
            upload_start = time.time()
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                upload_futures = {}
                for idx in sorted(results.keys()):
                    if results[idx].get("success") and results[idx].get("image_bytes"):
                        future = executor.submit(
                            self._upload_to_s3,
                            results[idx]["image_bytes"],
                            idx,
                            conversation_id
                        )
                        upload_futures[future] = idx
                
                for future in as_completed(upload_futures):
                    idx = upload_futures[future]
                    try:
                        s3_url = future.result()
                        results[idx]["s3_url"] = s3_url
                        print(f"   ✅ Image {idx} uploaded")
                    except Exception as e:
                        results[idx]["success"] = False
                        results[idx]["error"] = f"S3 upload failed: {str(e)}"
                        print(f"   ❌ Image {idx} upload failed: {str(e)}")
            
            upload_time = time.time() - upload_start
            print(f"☁️ Upload completed in {upload_time:.2f}s")

        total_time = time.time() - start_time
        print(f"\n⚡ Total time: {total_time:.2f}s")

        # Format response
        success_count = sum(1 for r in results.values() if r.get("success") and r.get("s3_url"))
        s3_urls = [results[idx].get('s3_url') for idx in sorted(results.keys()) if results[idx].get("success") and results[idx].get('s3_url')]
        
        if success_count == 4 and len(s3_urls) == 4:
            response = f"✅ SUCCESS: All 4 images generated in {total_time:.2f}s!\n\n[S3_URLS]\n"
            response += "\n".join(s3_urls)
            response += "\n[/S3_URLS]"
            return response
        else:
            response = f"⚠️ PARTIAL SUCCESS: {success_count}/4 images generated\n\n"
            for idx in sorted(results.keys()):
                if results[idx].get("success") and results[idx].get("s3_url"):
                    response += f"✅ Image {idx}: {results[idx].get('s3_url')}\n"
                else:
                    response += f"❌ Image {idx}: {results[idx].get('error', 'Unknown error')}\n"
            return response

    def _download_image(self, url: str) -> Image.Image:
        """Download image from URL and return PIL Image"""
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))

    def _generate_single_image(
        self,
        client: genai.Client,  # Reuse client (optimization #1)
        person_img: Image.Image,
        product_img: Image.Image,
        prompt: str,
        image_index: int
    ) -> dict:
        """
        Generate a single UGC image using Google Gemini (called in parallel).
        Returns dict with success status and image bytes (no S3 upload here).
        """
        try:
            from google.genai import types
            
            # Simple, direct prompt - let the model naturally blend the two images
            full_prompt = (
                f"Create a realistic UGC photo of this person holding and showcasing this product. "
                f"{prompt}. "
                f"Keep the person's face and identity exactly as shown. Natural lighting, casual UGC style."
            )

            print(f"   🎨 Generating image {image_index} with identity lock...")
            
            # Call Gemini API with proper config for image generation
            # Try with person image FIRST (as primary subject), product SECOND (as reference)
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model="gemini-3-pro-image-preview",
                        contents=[person_img, product_img, full_prompt],  # Person FIRST, then product, then prompt
                        config=types.GenerateContentConfig(
                            response_modalities=['TEXT', 'IMAGE'],
                            image_config=types.ImageConfig(
                                aspect_ratio="9:16",  # Vertical format for UGC/social media
                                image_size="1K"  # Optimization #2: 1K for speed
                            )
                        )
                    )
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"   ⚠️ Retry {attempt + 1}/{max_retries} for image {image_index}")
                        time.sleep(1)
                    else:
                        raise e

            # Extract generated image from response
            image_bytes = None
            
            # Try different response structures
            if hasattr(response, 'candidates') and response.candidates:
                # Response has candidates
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data is not None:
                                # Extract image bytes directly from inline_data
                                image_bytes = part.inline_data.data
                                break
                    if image_bytes:
                        break
            elif hasattr(response, 'parts'):
                # Direct parts access
                for part in response.parts:
                    if hasattr(part, 'inline_data') and part.inline_data is not None:
                        # Extract image bytes directly from inline_data
                        image_bytes = part.inline_data.data
                        break

            if not image_bytes:
                return {"success": False, "error": "No image data in response"}

            # Return bytes only, S3 upload happens later (optimization #4)
            return {"success": True, "image_bytes": image_bytes}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _upload_to_s3(
        self,
        image_bytes: bytes,
        image_index: int,
        conversation_id: str
    ) -> str:
        """
        Upload image bytes to S3 (called in batch after generation).
        Returns S3 URL.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_filename = f"generated_ugc_{timestamp}_{image_index}.png"
        s3_key = f"{S3_FOLDER_PREFIX}/generated/{conversation_id}/{s3_filename}"
        
        return upload_bytes_to_s3(image_bytes, s3_key, "image/png", public_read=False)
