"""
OCR service using AIML API (Google Cloud Document AI).
"""
import base64
import httpx
from pathlib import Path
from typing import Tuple

from ...core.config import get_settings

settings = get_settings()


class OCRService:
    """Service for OCR using AIML API."""
    
    def __init__(self):
        self.api_key = settings.aiml_api_key
        self.base_url = "https://api.aimlapi.com/v1/ocr"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.enabled = settings.ocr_enabled
        
        if not self.api_key:
            print("⚠️ AIML_API_KEY not found. OCR will be disabled.")
            self.enabled = False
    
    def _get_mime_type(self, file_path: str) -> str:
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/pdf"
        
    def _encode_file(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def extract_text(self, file_path: str) -> str:
        """
        Extract text from file using AIML OCR API.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Extracted text (markdown format)
        """
        if not self.enabled:
            return ""
            
        try:
            print(f"🔍 Sending {Path(file_path).name} to AIML OCR (google/gc-document-ai)...")
            
            # Prepare payload
            encoded_file = self._encode_file(file_path)
            mime_type = self._get_mime_type(file_path)
            
            payload = {
                "model": "google/gc-document-ai",
                "document": encoded_file,
                "mimeType": mime_type
            }
            
            # Make API call
            with httpx.Client() as client:
                response = client.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=60.0  # Increased timeout for OCR
                )
                
                if response.status_code != 201 and response.status_code != 200:
                    print(f"❌ OCR API Error: {response.status_code} - {response.text}")
                    return ""
                
                result = response.json()
                
                # Debug logging
                print(f"🔍 API Response Keys: {list(result.keys())}")
                
                # Method 1: Get text from root field (Google Document AI standard)
                if "text" in result and result["text"]:
                    final_text = result["text"]
                    print(f"✅ OCR completed (from root): {len(final_text)} characters extracted")
                    return final_text
                
                # Method 2: Parse pages (fallback)
                all_text = []
                if "pages" in result:
                    for page in result["pages"]:
                        if "markdown" in page:
                            all_text.append(page["markdown"])
                        elif "text" in page:
                            all_text.append(page["text"])
                
                if all_text:
                    final_text = "\n\n".join(all_text)
                    print(f"✅ OCR completed (from pages): {len(final_text)} characters extracted")
                    return final_text
                
                print("⚠️ No text found in API response")
                return ""
                
        except Exception as e:
            print(f"❌ OCR failed: {e}")
            return ""

    def should_use_ocr(self, extracted_text: str) -> bool:
        """
        Determine if OCR should be used based on extracted text length.
        
        Args:
            extracted_text: Text extracted by pdfplumber
        
        Returns:
            True if OCR should be used
        """
        if not self.enabled:
            return False
        
        text_length = len(extracted_text.strip())
        threshold = settings.ocr_min_text_threshold
        
        should_ocr = text_length < threshold
        
        if should_ocr:
            print(f"⚠️ Extracted text too short ({text_length} chars < {threshold} threshold)")
            print("   Will use AIML OCR for better text extraction")
        
        return should_ocr
    
    def extract_with_fallback(self, pdf_path: str, pdfplumber_text: str) -> Tuple[str, bool]:
        """
        Extract text with automatic OCR fallback.
        
        Args:
            pdf_path: Path to PDF file
            pdfplumber_text: Text extracted by pdfplumber
        
        Returns:
            Tuple of (extracted_text, used_ocr)
        """
        # Check if OCR is needed
        if not self.should_use_ocr(pdfplumber_text):
            return pdfplumber_text, False
        
        # Use OCR
        ocr_text = self.extract_text(pdf_path)
        
        # If OCR produced text, use it; otherwise fall back to pdfplumber
        if ocr_text and len(ocr_text.strip()) > len(pdfplumber_text.strip()):
            print("✅ Using AIML OCR text (better quality)")
            return ocr_text, True
        else:
            print("⚠️ OCR didn't improve text quality (or failed), using pdfplumber text")
            return pdfplumber_text, False


# Global OCR service instance
ocr_service = OCRService()
