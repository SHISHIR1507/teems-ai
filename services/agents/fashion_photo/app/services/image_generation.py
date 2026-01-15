import requests
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import contextvars
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from crewai.tools import BaseTool
from app.core.config import settings

@traceable(run_type="tool", name="AIML_Image_Generation_Call")
def call_image_api(prompt: str, image_urls: List[str], angle: str = ""):
    api_key = settings.AIML_API_KEY
    url = "https://api.aimlapi.com/v1/images/generations"
    
    # LangSmith Metadata
    rt = get_current_run_tree()
    if rt:
        rt.add_metadata({"model": "google/nano-banana-pro-edit", "angle": angle})
    
    identity_guard = "Maintain exact facial features of the avatars provided. Keep the apparels identical to the reference photos."
    scene_guard = "Photorealistic, high-end fashion photography, 85mm lens, cinematic lighting from different angles -Front -Back -Side Profile -In Motion Walking Shot."
    structure_guard = "Single image, no collage, no grid, no split screen, full frame."
    
    final_prompt = f"{angle} shot. {structure_guard} {identity_guard} {scene_guard} {prompt}"
    
    payload = {
        "model": "google/nano-banana-pro-edit",
        "prompt": final_prompt,
        "image_urls": image_urls,
        "num_images": 4
    }
    
    response = requests.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload)
    if response.status_code != 200:
        raise Exception(f"Image API Error: {response.text}")
    
    return response.json()

class ImageGenerationTool(BaseTool):
    name: str = "image_generation_tool"
    description: str = "Generates high-fashion images. Input: prompt (str), image_urls (list)."
    
    def _run(self, prompt: str, image_urls: List[str]) -> str:
        angles = ["Front View", "Back View", "Side Profile", "In Motion Walking Shot", "Close Up"]
        all_urls = []
        errors = []
        
        # Parallelize generation
        with ThreadPoolExecutor(max_workers=5) as executor:
            ctx = contextvars.copy_context()
            
            def run_in_context(p, u, a):
                return ctx.run(call_image_api, p, u, a)
            
            future_to_angle = {
                executor.submit(run_in_context, prompt, image_urls, angle): angle
                for angle in angles
            }
            
            for future in as_completed(future_to_angle):
                angle = future_to_angle[future]
                try:
                    result = future.result()
                    urls = [item.get('url') for item in result.get('data', [])]
                    all_urls.extend(urls)
                except Exception as e:
                    errors.append(f"{angle}: {str(e)}")
        
        if not all_urls and errors:
            return f"Errors: {'; '.join(errors)}"
        
        print(f"DEBUG: Generated {len(all_urls)} images: {all_urls}")
        return f"GENERATED_URLS: {all_urls}"
