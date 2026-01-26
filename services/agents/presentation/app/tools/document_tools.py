"""
CrewAI Tools for Document Upload and Processing
"""
from crewai.tools import tool
from app.services.slidespeak_client import get_slidespeak_client


@tool
def upload_document_to_slidespeak(document_url: str) -> str:
    """
    Upload a document (PDF, Word, etc.) to SlideSpeak for processing.
    
    Use this tool when the user wants to upload a document that will be used to generate a presentation.
    The document must be publicly accessible via URL (e.g., S3 URL).
    
    After uploading, use check_document_processing_status to wait for processing to complete,
    then use generate_presentation_from_document with the document_id.
    
    Args:
        document_url: Publicly accessible URL to the document (PDF, DOCX, etc.) (required)
    
    Returns:
        Document ID and status information
    """
    try:
        client = get_slidespeak_client()
        result = client.upload_document(document_url=document_url)
        
        document_id = result.get("document_id") or result.get("data", {}).get("document_id")
        if not document_id:
            return f"❌ Error: No document_id returned. Response: {result}"
        
        return f"""✅ Document uploaded successfully!

Document ID: {document_id}
Document URL: {document_url}
Status: processing

The document is being processed. Use check_document_processing_status tool with document_id="{document_id}" to check when it's ready.
Once status is "ready", use generate_presentation_from_document with this document_id."""
        
    except Exception as e:
        return f"❌ Failed to upload document: {str(e)}"


@tool
def check_document_processing_status(document_id: str) -> str:
    """
    Check if an uploaded document has finished processing and is ready for presentation generation.
    
    Use this tool after upload_document_to_slidespeak to check if the document is ready.
    Keep checking until status is "ready" before using generate_presentation_from_document.
    
    Args:
        document_id: The document ID from upload_document_to_slidespeak (required)
    
    Returns:
        Processing status and readiness information
    """
    try:
        client = get_slidespeak_client()
        result = client.check_document_status(document_id=document_id)
        
        status = result.get("status") or result.get("data", {}).get("status", "unknown")
        
        if status == "ready":
            return f"""✅ Document is ready!

Document ID: {document_id}
Status: ready

You can now use generate_presentation_from_document with document_id="{document_id}"."""
        elif status == "processing":
            return f"""⏳ Document is still processing...

Document ID: {document_id}
Status: processing

Please wait and check again in a few moments using check_document_processing_status with document_id="{document_id}"."""
        elif status == "failed":
            error = result.get("error") or result.get("data", {}).get("error", "Unknown error")
            return f"""❌ Document processing failed

Document ID: {document_id}
Status: failed
Error: {error}

Please try uploading the document again."""
        else:
            return f"""Document Status:

Document ID: {document_id}
Status: {status}

Response: {result}"""
        
    except Exception as e:
        return f"❌ Failed to check document status: {str(e)}"
