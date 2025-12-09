
import io
import torch
import fitz  # PyMuPDF
from PIL import Image
from fastapi import UploadFile
from transformers import AutoProcessor, AutoModelForImageTextToText
import google.generativeai as genai

# ========== SUNIL'S ORIGINAL CODE (MINIMAL CHANGES) ==========

def load_ocr():
    """Sunil's original function"""
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


def load_vision_model(api_key: str = None):
    """Sunil's function - just need API key parameter"""
    if not api_key:
        print("Gemini API key missing — scene description disabled")
        return None

    genai.configure(api_key=api_key)
    print("Gemini Vision model loaded!")
    return genai.GenerativeModel("gemini-2.5-flash")


def pdf_to_images(pdf_bytes: bytes, dpi=300):
    """Sunil's function - takes bytes instead of file path"""
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
    """Sunil's original function - NO CHANGES"""
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


def describe_scene(image, gemini_model):
    """Sunil's original function - NO CHANGES"""
    if not gemini_model:
        return ""

    prompt = """
    You are a scientific visual analysis assistant.
    Describe the diagram or figure in the image in a technical manner.
    Ignore only-text content and focus on the visual meaning.
    """
    response = gemini_model.generate_content([prompt, image])
    return response.text.strip()


# ========== SIMPLE WRAPPERS FOR UploadFile ==========

async def process_uploaded_image(file: UploadFile, gemini_api_key: str = None) -> str:
    """Simple wrapper for Sunil's process_image()"""
    contents = await file.read()
    
    # Load models
    processor, model, device = load_ocr()
    gemini_model = load_vision_model(gemini_api_key)
    
    # Convert to image
    img = Image.open(io.BytesIO(contents)).convert("RGB")
    
    # Use Sunil's functions
    text = ocr_image(img, processor, model, device)
    scene = describe_scene(img, gemini_model)
    
    if scene:
        return f"{text}\n\n[Diagram]: {scene}"
    return text


async def process_uploaded_pdf(file: UploadFile, gemini_api_key: str = None) -> str:
    """Simple wrapper for Sunil's process_pdf()"""
    contents = await file.read()
    
    # Load models
    processor, model, device = load_ocr()
    gemini_model = load_vision_model(gemini_api_key)
    
    # Convert PDF to images
    pages = pdf_to_images(contents)
    
    # OCR each page
    results = []
    for i, img in enumerate(pages, start=1):
        print(f"OCR Page {i}/{len(pages)}...")
        text = ocr_image(img, processor, model, device)
        results.append(f"--- Page {i} ---\n{text}")
    
    return "\n\n".join(results)