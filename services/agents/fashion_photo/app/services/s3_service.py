import uuid
import boto3
from app.core.config import settings

# Use explicit credentials if provided, otherwise use IAM role (when running on ECS)
client_kwargs = {'region_name': settings.AWS_REGION}
if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
    client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
    client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY

S3_CLIENT = boto3.client('s3', **client_kwargs)

def upload_to_s3(file_content: bytes, folder_type: str, extension: str = "png") -> str:
    """
    Upload file to S3.
    folder_type: 'user_uploaded' or 'ai_generated'
    """
    file_name = f"{uuid.uuid4().hex}.{extension}"
    key = f"photographer_agent/{folder_type}/{file_name}"
    
    S3_CLIENT.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=file_content,
        ContentType=f"image/{extension}"
    )
    return f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/{key}"
