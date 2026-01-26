"""
S3 utilities for uploading and managing files in AWS S3
Uses boto3 for S3 operations
Supports both explicit credentials and IAM roles (for ECS)
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional
import mimetypes
from datetime import datetime, timedelta
from app.core.config import get_settings

settings = get_settings()

# Initialize S3 client
if settings.aws_access_key_id and settings.aws_secret_access_key:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region
    )
else:
    # Use IAM role (ECS task role will be used automatically)
    s3_client = boto3.client('s3', region_name=settings.aws_region)


def upload_bytes_to_s3(
    file_bytes: bytes,
    s3_key: str,
    content_type: str = 'application/octet-stream',
    public_read: bool = False
) -> str:
    """
    Upload bytes directly to S3
    
    Args:
        file_bytes: File content as bytes
        s3_key: S3 object key (path in bucket)
        content_type: MIME type
        public_read: If True, makes the file publicly readable
    
    Returns:
        S3 URL of the uploaded file
    """
    try:
        extra_args = {
            'ContentType': content_type
        }
        
        if public_read:
            extra_args['ACL'] = 'public-read'
        
        s3_client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=file_bytes,
            **extra_args
        )
        
        s3_url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
        print(f"✅ Uploaded to S3: {s3_url}")
        return s3_url
        
    except ClientError as e:
        error_msg = f"Failed to upload to S3: {str(e)}"
        print(f"❌ {error_msg}")
        raise Exception(error_msg)


def generate_presigned_url(
    s3_key: str,
    expiration: int = 3600,
    http_method: str = 'GET'
) -> str:
    """
    Generate a presigned URL for S3 object
    
    Args:
        s3_key: S3 object key
        expiration: URL expiration time in seconds (default 1 hour)
        http_method: HTTP method (GET, PUT, etc.)
    
    Returns:
        Presigned URL
    """
    try:
        url = s3_client.generate_presigned_url(
            'get_object' if http_method == 'GET' else 'put_object',
            Params={'Bucket': settings.s3_bucket_name, 'Key': s3_key},
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        error_msg = f"Failed to generate presigned URL: {str(e)}"
        print(f"❌ {error_msg}")
        raise Exception(error_msg)


def delete_file_from_s3(s3_key: str) -> bool:
    """
    Delete a file from S3
    
    Args:
        s3_key: S3 object key
    
    Returns:
        True if successful
    """
    try:
        s3_client.delete_object(Bucket=settings.s3_bucket_name, Key=s3_key)
        print(f"✅ Deleted from S3: {s3_key}")
        return True
    except ClientError as e:
        error_msg = f"Failed to delete from S3: {str(e)}"
        print(f"❌ {error_msg}")
        return False


def get_s3_key_for_video(conversation_id: str, filename: str) -> str:
    """
    Generate S3 key for video upload
    """
    import uuid
    from pathlib import Path
    ext = Path(filename).suffix or '.mp4'
    unique_name = f"{uuid.uuid4()}{ext}"
    return f"{settings.s3_folder_prefix}/videos/{conversation_id}/{unique_name}"


def get_s3_key_for_content(conversation_id: str, filename: str, asset_type: str = "video") -> str:
    """Generate S3 key for content upload (image or video)."""
    import uuid
    from pathlib import Path
    ext = Path(filename).suffix
    if not ext:
        ext = ".mp4" if asset_type == "video" else ".jpg"
    unique_name = f"{uuid.uuid4()}{ext}"
    folder = "videos" if asset_type == "video" else "images"
    return f"{settings.s3_folder_prefix}/content/{folder}/{conversation_id}/{unique_name}"
