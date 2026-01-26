"""
S3 utilities for uploading and managing files in AWS S3
Uses boto3 for S3 operations
Supports both explicit credentials and IAM roles (for ECS)
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional
import mimetypes
from datetime import datetime
from app.core.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    S3_BUCKET_NAME,
    S3_FOLDER_PREFIX
)

# Initialize S3 client
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
else:
    # Use IAM role (ECS task role will be used automatically)
    s3_client = boto3.client('s3', region_name=AWS_REGION)


def upload_file_to_s3(
    file_path: str,
    s3_key: str,
    content_type: Optional[str] = None,
    public_read: bool = False
) -> str:
    """
    Upload a file to S3 bucket
    
    Args:
        file_path: Local path to the file
        s3_key: S3 object key (path in bucket)
        content_type: MIME type (auto-detected if not provided)
        public_read: If True, makes the file publicly readable
    
    Returns:
        S3 URL of the uploaded file
    """
    try:
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'application/octet-stream'
        
        extra_args = {
            'ContentType': content_type
        }
        
        s3_client.upload_file(
            file_path,
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs=extra_args
        )
        
        s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        print(f"✅ Uploaded to S3: {s3_url}")
        return s3_url
        
    except ClientError as e:
        error_msg = f"Failed to upload {file_path} to S3: {str(e)}"
        print(f"❌ {error_msg}")
        raise Exception(error_msg)


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
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type
        )
        
        s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        print(f"✅ Uploaded bytes to S3: {s3_url}")
        return s3_url
        
    except ClientError as e:
        error_msg = f"Failed to upload bytes to S3: {str(e)}"
        print(f"❌ {error_msg}")
        raise Exception(error_msg)


def generate_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    """
    Generate a presigned URL for temporary access to a private S3 object
    
    Args:
        s3_key: S3 object key
        expiration: URL expiration time in seconds (default 1 hour)
    
    Returns:
        Presigned URL
    """
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        print(f"❌ Failed to generate presigned URL: {str(e)}")
        raise Exception(f"Failed to generate presigned URL: {str(e)}")


def delete_file_from_s3(s3_key: str) -> bool:
    """
    Delete a file from S3
    
    Args:
        s3_key: S3 object key
    
    Returns:
        True if successful, False otherwise
    """
    try:
        s3_client.delete_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )
        print(f"✅ Deleted from S3: {s3_key}")
        return True
    except ClientError as e:
        print(f"❌ Failed to delete from S3: {str(e)}")
        return False


def get_s3_key_for_upload(conversation_id: str, filename: str, asset_type: str) -> str:
    """
    Generate S3 key (path) for uploaded files
    
    Args:
        conversation_id: Conversation UUID
        filename: Original filename
        asset_type: Type of asset ('document', 'presentation', 'brand_logo')
    
    Returns:
        S3 key path with folder prefix
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if asset_type == 'document':
        return f"{S3_FOLDER_PREFIX}/uploads/{conversation_id}/{timestamp}_{filename}"
    elif asset_type == 'presentation':
        return f"{S3_FOLDER_PREFIX}/presentations/{conversation_id}/{timestamp}_{filename}"
    elif asset_type == 'brand_logo':
        return f"{S3_FOLDER_PREFIX}/brand_assets/logos/{timestamp}_{filename}"
    else:
        return f"{S3_FOLDER_PREFIX}/assets/{conversation_id}/{filename}"


def download_from_url_to_s3(url: str, s3_key: str, content_type: Optional[str] = None) -> str:
    """
    Download a file from URL and upload to S3
    
    Args:
        url: Source URL
        s3_key: Destination S3 key
        content_type: MIME type (auto-detected if not provided)
    
    Returns:
        S3 URL of the uploaded file
    """
    import requests
    
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        
        if not content_type:
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
        
        file_bytes = response.content
        return upload_bytes_to_s3(file_bytes, s3_key, content_type)
        
    except Exception as e:
        error_msg = f"Failed to download and upload to S3: {str(e)}"
        print(f"❌ {error_msg}")
        raise Exception(error_msg)
