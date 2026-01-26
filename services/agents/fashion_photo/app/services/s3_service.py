"""
S3 service for file uploads
"""
import uuid
import boto3
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("services.s3")

# Initialize S3 client (lazy)
_s3_client = None


def get_s3_client():
    """Get or create S3 client"""
    global _s3_client
    if _s3_client is None:
        settings = get_settings()
        client_kwargs = {'region_name': settings.aws_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs['aws_access_key_id'] = settings.aws_access_key_id
            client_kwargs['aws_secret_access_key'] = settings.aws_secret_access_key
        
        _s3_client = boto3.client('s3', **client_kwargs)
    return _s3_client


def upload_to_s3(file_content: bytes, folder_type: str, extension: str = "png") -> str:
    """
    Upload file to S3.
    
    Args:
        file_content: File content as bytes
        folder_type: 'user_uploaded' or 'ai_generated'
        extension: File extension (default: 'png')
    
    Returns:
        S3 URL of uploaded file
    """
    settings = get_settings()
    s3_client = get_s3_client()
    
    file_name = f"{uuid.uuid4().hex}.{extension}"
    key = f"{settings.s3_folder_prefix}/{folder_type}/{file_name}"
    
    try:
        s3_client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=key,
            Body=file_content,
            ContentType=f"image/{extension}"
        )
        s3_url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{key}"
        logger.info(f"Uploaded to S3: {s3_url}")
        return s3_url
    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        raise
