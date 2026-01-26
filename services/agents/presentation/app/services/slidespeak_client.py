"""
SlideSpeak API client wrapper
Handles all API interactions with SlideSpeak
"""
import requests
from typing import Dict, Optional, Any
from app.core.config import SLIDESPEAK_API_KEY, SLIDESPEAK_BASE_URL


class SlideSpeakClient:
    """Client for interacting with SlideSpeak API"""
    
    def __init__(self):
        self.api_key = SLIDESPEAK_API_KEY
        self.base_url = SLIDESPEAK_BASE_URL.rstrip('/')
        if not self.api_key:
            raise ValueError("SLIDESPEAK_API_KEY is required")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to SlideSpeak API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        headers.update(kwargs.pop('headers', {}))
        
        try:
            response = requests.request(method, url, headers=headers, timeout=60, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"SlideSpeak API error: {str(e)}"
            if hasattr(e.response, 'text'):
                error_msg += f" - {e.response.text}"
            raise Exception(error_msg)
    
    # Generation endpoints
    def generate_presentation(
        self,
        plain_text: Optional[str] = None,
        document_id: Optional[str] = None,
        length: int = 6,
        template: str = "default",
        tone: str = "professional",
        verbosity: str = "standard",
        language: str = "ORIGINAL",
        fetch_images: bool = True,
        custom_user_instructions: Optional[str] = None,
        use_branding_logo: bool = False,
        use_branding_color: bool = False
    ) -> Dict[str, Any]:
        """Generate a presentation"""
        payload = {
            "length": length,
            "template": template,
            "tone": tone,
            "verbosity": verbosity,
            "language": language,
            "fetch_images": fetch_images,
            "use_branding_logo": use_branding_logo,
            "use_branding_color": use_branding_color
        }
        
        if plain_text:
            payload["plain_text"] = plain_text
        elif document_id:
            payload["document_id"] = document_id
        else:
            raise ValueError("Either plain_text or document_id must be provided")
        
        if custom_user_instructions:
            payload["custom_user_instructions"] = custom_user_instructions
        
        return self._make_request("POST", "/presentation/generate", json=payload)
    
    def generate_slide_by_slide(self, slides: list, template: str = "default") -> Dict[str, Any]:
        """Generate presentation slide by slide"""
        payload = {
            "slides": slides,
            "template": template
        }
        return self._make_request("POST", "/presentation/generate/slide-by-slide", json=payload)
    
    # Editing endpoints
    def edit_presentation(self, presentation_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Edit an existing presentation"""
        payload = {
            "presentation_id": presentation_id,
            "updates": updates
        }
        return self._make_request("POST", "/presentation/edit", json=payload)
    
    def edit_slide(
        self,
        presentation_id: str,
        action: str,
        slide_index: Optional[int] = None,
        content: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Edit a slide (insert, regenerate, or remove)"""
        payload = {
            "presentation_id": presentation_id,
            "action": action
        }
        if slide_index is not None:
            payload["slide_index"] = slide_index
        if content:
            payload["content"] = content
        return self._make_request("POST", "/presentation/edit/slide", json=payload)
    
    # Document endpoints
    def upload_document(self, document_url: str) -> Dict[str, Any]:
        """Upload a document for processing"""
        payload = {
            "document_url": document_url
        }
        return self._make_request("POST", "/document/upload", json=payload)
    
    def check_document_status(self, document_id: str) -> Dict[str, Any]:
        """Check document processing status"""
        return self._make_request("GET", f"/document/status/{document_id}")
    
    # Template endpoints
    def get_templates(self) -> Dict[str, Any]:
        """Get all available templates"""
        return self._make_request("GET", "/presentation/templates")
    
    def get_branded_templates(self) -> Dict[str, Any]:
        """Get branded templates"""
        return self._make_request("GET", "/presentation/templates/branded")
    
    # Download endpoint
    def get_download_url(self, presentation_id: str) -> Dict[str, Any]:
        """Get download URL for a presentation"""
        return self._make_request("GET", f"/presentations/{presentation_id}/download")
    
    # Task status
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Check task status"""
        return self._make_request("GET", f"/task_status/{task_id}")
    
    # User info
    def get_me(self) -> Dict[str, Any]:
        """Get user info and credits"""
        return self._make_request("GET", "/me")
    
    # Webhook endpoints
    def subscribe_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """Subscribe to webhooks"""
        payload = {
            "webhook_url": webhook_url
        }
        return self._make_request("POST", "/webhook/subscribe", json=payload)
    
    def unsubscribe_webhook(self) -> Dict[str, Any]:
        """Unsubscribe from webhooks"""
        return self._make_request("DELETE", "/webhook/unsubscribe")


# Singleton instance
_client_instance = None

def get_slidespeak_client() -> SlideSpeakClient:
    """Get or create SlideSpeak client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = SlideSpeakClient()
    return _client_instance
