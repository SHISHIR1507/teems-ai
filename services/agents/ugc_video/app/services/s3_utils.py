"""
S3 utilities for uploading and managing files in AWS S3
Uses boto3 for S3 operations
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
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)


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
        public_read: If True, makes the file publicly readable (for AI/ML API access)
                     Note: Requires bucket policy to allow public access, not ACLs
    
    Returns:
        S3 URL of the uploaded file
    
    Raises:
        Exception if upload fails
    """
    try:
        # Auto-detect content type if not provided
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'application/octet-stream'
        
        # Upload file without ACL (bucket policy controls access)
        extra_args = {
            'ContentType': content_type
        }
        
        s3_client.upload_file(
            file_path,
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs=extra_args
        )
        
        # Generate S3 URL
        s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        
        access_note = "public" if public_read else "bucket-policy-controlled"
        print(f"✅ Uploaded to S3 ({access_note}): {s3_url}")
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
    Upload bytes directly to S3 (useful for uploaded files)
    
    Args:
        file_bytes: File content as bytes
        s3_key: S3 object key (path in bucket)
        content_type: MIME type
        public_read: If True, makes the file publicly readable (for AI/ML API access)
                     Note: Requires bucket policy to allow public access, not ACLs
    
    Returns:
        S3 URL of the uploaded file
    """
    try:
        # Upload without ACL (bucket policy controls access)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type
        )
        
        s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        access_note = "public" if public_read else "bucket-policy-controlled"
        print(f"✅ Uploaded bytes to S3 ({access_note}): {s3_url}")
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
        asset_type: Type of asset ('person', 'product', 'audio', 'script')
    
    Returns:
        S3 key path with folder prefix
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Add folder prefix to all paths
    if asset_type in ['person', 'product']:
        return f"{S3_FOLDER_PREFIX}/uploads/{conversation_id}/{asset_type}_{timestamp}_{filename}"
    elif asset_type == 'audio':
        return f"{S3_FOLDER_PREFIX}/audio/{conversation_id}/{filename}"
    elif asset_type == 'script':
        return f"{S3_FOLDER_PREFIX}/scripts/{conversation_id}/{filename}"
    else:
        return f"{S3_FOLDER_PREFIX}/assets/{conversation_id}/{filename}"


# Test function
if __name__ == "__main__":
    print(f"S3 Bucket: {S3_BUCKET_NAME}")
    print(f"AWS Region: {AWS_REGION}")
    print(f"AWS Access Key ID: {AWS_ACCESS_KEY_ID[:10]}..." if AWS_ACCESS_KEY_ID else "Not set")
    
    # Test S3 key generation
    test_key = get_s3_key_for_upload("test-conv-123", "person.jpg", "person")
    print(f"Example S3 key: {test_key}")
