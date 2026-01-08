import requests
import base64
import os
from crewai.tools import BaseTool
from typing import Type, List, Optional
from pydantic import BaseModel, Field
import langsmith
from langsmith import traceable
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

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
    description: str = "Generates 4 UGC-style images in parallel where a person is showcasing a product. Takes S3 URLs and a list of 4 prompts, generates all images concurrently."
    args_schema: Type[BaseModel] = BananaUGCInput

    @traceable(
        name="banana_ugc_tool_parallel",
        tags=["image-generation", "banana-api", "ugc", "parallel"],
        metadata={"model": "google/nano-banana-pro-edit", "provider": "aiml-api", "num_images": 4}
    )
    def _run(
        self,
        person_image_url: str,
        product_image_url: str,
        prompts: List[str],
        conversation_id: Optional[str] = None,
        upload_to_s3: bool = False
    ) -> str:
        """
        Generate 4 UGC images in parallel using AI/ML API with google/nano-banana-pro model.
        Uses S3 URLs directly - no local file I/O or base64 encoding needed.
        Each prompt gets its own API call, all executed concurrently.
        """
        if len(prompts) != 4:
            return f"Error: Expected exactly 4 prompts, got {len(prompts)}"

        api_key = os.getenv("AIML_API_KEY")
        if not api_key:
            return "Error: AIML_API_KEY not found in environment variables"

        # Validate URLs
        with langsmith.trace(
            name="validate_image_urls",
            inputs={
                "person_image_url": person_image_url,
                "product_image_url": product_image_url
            },
            tags=["validation", "s3-urls"],
            metadata={}
        ) as validate_trace:
            if not person_image_url.startswith('http'):
                error_msg = f"Error: Invalid person image URL: {person_image_url}"
                validate_trace.outputs = {"error": error_msg}
                return error_msg
            
            if not product_image_url.startswith('http'):
                error_msg = f"Error: Invalid product image URL: {product_image_url}"
                validate_trace.outputs = {"error": error_msg}
                return error_msg
            
            validate_trace.outputs = {"status": "urls_validated"}
            print(f"✅ Using S3 URLs directly (no file I/O needed)")

        # Generate images in parallel
        print(f"\n🚀 Starting parallel generation of 4 images...")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all 4 API calls concurrently
            futures = {}
            for idx, prompt in enumerate(prompts, 1):
                future = executor.submit(
                    self._generate_single_image,
                    person_image_url,
                    product_image_url,
                    prompt,
                    f"generated_ugc_image_{idx}.png",
                    idx,
                    api_key,
                    conversation_id,
                    upload_to_s3
                )
                futures[future] = idx

            # Collect results as they complete
            results = {}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    results[idx] = result
                    print(f"✅ Image {idx}/4 completed")
                except Exception as e:
                    error_msg = f"Error generating image {idx}: {str(e)}"
                    results[idx] = {"success": False, "error": error_msg}
                    print(f"❌ Image {idx}/4 failed: {error_msg}")

        total_time = time.time() - start_time
        print(f"\n⚡ All 4 images generated in {total_time:.2f}s (parallel)")

        # Format response with S3 URLs
        success_count = sum(1 for r in results.values() if r.get("success"))
        s3_urls = []
        
        for idx in sorted(results.keys()):
            if results[idx].get("success") and results[idx].get('s3_url'):
                s3_urls.append(results[idx]['s3_url'])
        
        if success_count == 4 and len(s3_urls) == 4:
            # Return structured response with S3 URLs
            response = f"✅ SUCCESS: All 4 images generated and uploaded to S3!\n"
            response += f"Total time: {total_time:.2f}s\n\n"
            response += "[S3_URLS]\n"
            for url in s3_urls:
                response += f"{url}\n"
            response += "[/S3_URLS]"
            return response
        else:
            response = f"⚠️ PARTIAL SUCCESS: {success_count}/4 images generated, {len(s3_urls)}/4 uploaded to S3\n\n"
            for idx in sorted(results.keys()):
                if results[idx].get("success"):
                    result_data = results[idx]
                    if result_data.get('s3_url'):
                        response += f"✅ Image {idx}: {result_data['s3_url']}\n"
                    else:
                        response += f"⚠️ Image {idx}: Generated but S3 upload failed\n"
                else:
                    response += f"❌ Image {idx}: {results[idx].get('error', 'Unknown error')}\n"
            return response

    @traceable(
        name="generate_single_image",
        tags=["image-generation", "banana-api", "single-call"],
        metadata={"model": "google/nano-banana-pro-edit"}
    )
    def _generate_single_image(
        self,
        person_image_url: str,
        product_image_url: str,
        prompt: str,
        output_filename: str,
        image_index: int,
        api_key: str,
        conversation_id: Optional[str] = None,
        upload_to_s3: bool = False
    ) -> dict:
        """
        Generate a single UGC image (called in parallel by ThreadPoolExecutor).
        Uses S3 URLs directly - no file I/O or base64 encoding.
        Returns dict with success status and S3 URL or error.
        """

        # AI/ML API endpoint
        url = "https://api.aimlapi.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Construct prompt for image-to-image composition
        full_prompt = (
            f"Combine these images to create a realistic UGC-style photo where the person "
            f"from the first image is naturally showcasing the product from the second image. "
            f"{prompt}. Keep the same person's face and identity, and the exact product appearance. "
            f"Make it look like authentic user-generated content."
        )

        # Use S3 URLs directly (no base64 encoding needed!)
        payload = {
            "model": "google/nano-banana-pro-edit",
            "prompt": full_prompt,
            "image_urls": [
                person_image_url,  # Direct S3 URL
                product_image_url  # Direct S3 URL
            ],
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "num_images": 1
        }

        # Call image generation API with detailed tracing
        with langsmith.trace(
            name=f"call_banana_api_image_{image_index}",
            inputs={
                "model": "google/nano-banana-pro-edit",
                "prompt": full_prompt,
                "image_index": image_index,
                "person_image_url": person_image_url,
                "product_image_url": product_image_url
            },
            tags=["api-call", "image-generation", "aiml-api", "s3-urls"],
            metadata={
                "provider": "AI/ML API",
                "endpoint": url,
                "model": "google/nano-banana-pro-edit",
                "image_index": image_index,
                "uses_s3_urls": True
            }
        ) as api_trace:
            try:
                call_start = time.time()

                print(f"   🎨 Calling API for image {image_index} (using S3 URLs)...")
                
                response = requests.post(url, json=payload, headers=headers, timeout=180)

                latency = time.time() - call_start

                # Log API call metadata
                api_trace.metadata.update({
                    "status_code": response.status_code,
                    "latency_seconds": round(latency, 2),
                    "response_size_bytes": len(response.content)
                })

                # Accept both 200 and 201 status codes
                if response.status_code not in [200, 201]:
                    error_msg = f"API returned status {response.status_code}: {response.text[:500]}"
                    api_trace.outputs = {"error": error_msg, "status_code": response.status_code}
                    return {"success": False, "error": error_msg}

                result = response.json()
                api_trace.outputs = {"status": "success", "result_keys": list(result.keys())}

                # Estimate cost
                estimated_cost = 0.02
                api_trace.metadata["estimated_cost_usd"] = estimated_cost

            except requests.exceptions.Timeout:
                error_msg = f"API request timed out after 180 seconds"
                api_trace.outputs = {"error": error_msg}
                return {"success": False, "error": error_msg}
            except requests.exceptions.RequestException as e:
                error_msg = f"Error calling AI/ML API: {str(e)[:200]}"
                api_trace.outputs = {"error": error_msg}
                return {"success": False, "error": error_msg}

        # Save the generated image
        with langsmith.trace(
            name=f"save_generated_image_{image_index}",
            tags=["image-output", "file-save", "s3-upload"],
            metadata={"image_index": image_index}
        ) as save_trace:
            if "data" in result and len(result["data"]) > 0:
                image_data = result["data"][0]

                # Check if it's a URL or base64
                if "url" in image_data:
                    # Download from URL
                    img_response = requests.get(image_data["url"])
                    img_response.raise_for_status()
                    image_bytes = img_response.content

                    save_trace.metadata.update({
                        "method": "url_download",
                        "image_url": image_data["url"],
                        "image_size_bytes": len(image_bytes)
                    })

                elif "b64_json" in image_data:
                    # Decode base64
                    image_bytes = base64.b64decode(image_data["b64_json"])

                    save_trace.metadata.update({
                        "method": "base64_decode",
                        "image_size_bytes": len(image_bytes)
                    })
                else:
                    error_msg = f"Unexpected image format in response"
                    save_trace.outputs = {"error": error_msg}
                    return {"success": False, "error": error_msg}
                
                # Upload directly to S3 if requested (NO local file storage)
                s3_url = None
                if upload_to_s3 and conversation_id:
                    try:
                        from s3_utils import upload_bytes_to_s3
                        from datetime import datetime
                        import os as os_module
                        
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        s3_filename = f"generated_ugc_{timestamp}_{image_index}.png"
                        
                        # Get folder prefix from environment
                        s3_folder_prefix = os_module.getenv("S3_FOLDER_PREFIX", "UGC_Agent")
                        s3_key = f"{s3_folder_prefix}/generated/{conversation_id}/{s3_filename}"
                        
                        # Upload bytes directly to S3 (no local file!)
                        s3_url = upload_bytes_to_s3(
                            image_bytes, 
                            s3_key, 
                            "image/png",
                            public_read=False  # Keep private, use presigned URLs if needed
                        )
                        save_trace.metadata["s3_url"] = s3_url
                        print(f"   ☁️ Uploaded to S3: {s3_url}")
                        
                    except Exception as e:
                        print(f"   ⚠️ S3 upload failed: {str(e)}")
                        # Continue even if S3 upload fails
                else:
                    # If not uploading to S3, we have no local storage - return API URL
                    s3_url = image_data.get("url")
                    print(f"   ⚠️ S3 upload disabled, using API URL: {s3_url}")
                
                save_trace.outputs = {"s3_url": s3_url, "no_local_storage": True}

                return {"success": True, "s3_url": s3_url}

            else:
                error_msg = f"No image data in response"
                save_trace.outputs = {"error": error_msg}
                return {"success": False, "error": error_msg}
