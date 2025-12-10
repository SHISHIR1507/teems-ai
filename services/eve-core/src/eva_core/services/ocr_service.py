
import io
import base64
import torch
import fitz
from PIL import Image
from fastapi import UploadFile
from transformers import AutoProcessor, AutoModelForImageTextToText
from openai import AsyncOpenAI
from ..config import get_settings


def load_ocr():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32

    print(f"Loading OCR model... (device={device})")
    model_id = "stepfun-ai/GOT-OCR-2.0-hf"

    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        torch_dtype=dtype,
        device_map=device,
    )
    return processor, model, device


def get_vision_client():
    """Get AIML API client for vision models."""
    settings = get_settings()
    if not settings.aiml_api_key:
        print("AIML API key missing — scene description disabled")
        return None
    
    client = AsyncOpenAI(
        api_key=settings.aiml_api_key,
        base_url=settings.aiml_base_url,
    )
    print("AIML Vision model client loaded!")
    return client


def pdf_to_images(pdf_bytes: bytes, dpi=300):
    """Converts PDF bytes to a list of images at the specified DPI."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []

    for i, page in enumerate(doc):
        print(f"Rendering page {i + 1}/{len(doc)}...")
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pages.append(img)

    doc.close()
    return pages


def ocr_image(image, processor, model, device):
    inputs = processor(images=image, return_tensors="pt").to(device)

    generated_ids = model.generate(
        **inputs,
        do_sample=False,
        tokenizer=processor.tokenizer,
        stop_strings="<|im_end|>",
        max_new_tokens=4096,
    )

    return processor.batch_decode(
        generated_ids, skip_special_tokens=True
    )[0].strip()


async def describe_scene(image, vision_client):
    """Describe scene using AIML API vision model."""
    if not vision_client:
        return ""

    # Convert PIL Image to base64
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    img_data_url = f"data:image/png;base64,{img_base64}"

    prompt = """
    You are a scientific visual analysis assistant.
    Describe the diagram or figure in the image in a technical manner.
    Ignore only-text content and focus on the visual meaning.
    """
    
    try:
        response = await vision_client.chat.completions.create(
            model="google/gemini-2.0-flash-exp",  # Vision-capable model via AIML API
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": img_data_url}},
                    ],
                }
            ],
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Vision model error: {e}")
        return ""



async def process_uploaded_image(file: UploadFile) -> str:
    contents = await file.read()
    
    # Load models
    processor, model, device = load_ocr()
    vision_client = get_vision_client()
    
    # Convert to image
    img = Image.open(io.BytesIO(contents)).convert("RGB")
    
    text = ocr_image(img, processor, model, device)
    scene = await describe_scene(img, vision_client)
    
    if scene:
        return f"{text}\n\n[Diagram]: {scene}"
    return text


async def process_uploaded_pdf(file: UploadFile) -> str:
    """Converts PDF bytes to a list of images at the specified DPI."""
    contents = await file.read()
    
    # Load models
    processor, model, device = load_ocr()
    vision_client = get_vision_client()
    
    # Convert PDF to images
    pages = pdf_to_images(contents)
    
    # OCR each page
    results = []
    for i, img in enumerate(pages, start=1):
        print(f"OCR Page {i}/{len(pages)}...")
        text = ocr_image(img, processor, model, device)
        scene = await describe_scene(img, vision_client) if vision_client else ""
        page_result = f"--- Page {i} ---\n{text}"
        if scene:
            page_result += f"\n\n[Diagram]: {scene}"
        results.append(page_result)
    
    return "\n\n".join(results)