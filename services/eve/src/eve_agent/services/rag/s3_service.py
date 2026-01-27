"""
S3 service for uploading, downloading, and managing PDF files.
"""
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from typing import Optional, Tuple
import tempfile

from ...core.config import get_settings

settings = get_settings()


class S3Service:
    """Service for interacting with AWS S3."""
    
    def __init__(self):
        # Use IAM role credentials if available (ECS), otherwise use explicit credentials
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
        else:
            # Use default credentials (IAM role in ECS)
            self.s3_client = boto3.client('s3', region_name=settings.aws_region)
        self.bucket_name = settings.s3_bucket_name
        self.folder_prefix = settings.s3_folder_prefix
    
    def _generate_s3_key(self, filename: str, tenant_id: str) -> str:
        """
        Generate S3 key with timestamp and tenant_id to avoid conflicts.
        
        Format: UserUploads/{tenant_id}/{timestamp}_{filename}
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = filename.replace(" ", "_")
        return f"{self.folder_prefix}/{tenant_id}/{timestamp}_{safe_filename}"
    
    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: str,
        content_type: str = "application/pdf"
    ) -> Tuple[str, str]:
        """
        Upload file to S3.
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            tenant_id: Tenant ID for organization
            content_type: MIME type of the file
        
        Returns:
            Tuple of (s3_url, s3_key)
        
        Raises:
            Exception if upload fails
        """
        s3_key = self._generate_s3_key(filename, tenant_id)
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    'tenant_id': tenant_id,
                    'original_filename': filename,
                    'upload_timestamp': datetime.utcnow().isoformat()
                }
            )
            
            # Generate S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
            
            print(f"✅ Uploaded to S3: {s3_key}")
            return s3_url, s3_key
            
        except ClientError as e:
            print(f"❌ S3 upload failed: {e}")
            raise Exception(f"Failed to upload file to S3: {str(e)}")
    
    def download_file(self, s3_key: str) -> bytes:
        """
        Download file from S3.
        
        Args:
            s3_key: S3 object key
        
        Returns:
            File content as bytes
        
        Raises:
            Exception if download fails
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            content = response['Body'].read()
            print(f"✅ Downloaded from S3: {s3_key}")
            return content
            
        except ClientError as e:
            print(f"❌ S3 download failed: {e}")
            raise Exception(f"Failed to download file from S3: {str(e)}")
    
    def download_to_temp_file(self, s3_key: str, suffix: str = ".pdf") -> str:
        """
        Download file from S3 to a temporary file.
        
        Args:
            s3_key: S3 object key
            suffix: File extension for temp file
        
        Returns:
            Path to temporary file
        
        Note:
            Caller is responsible for deleting the temp file
        """
        content = self.download_file(s3_key)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            temp_path = tmp.name
        
        print(f"✅ Saved to temp file: {temp_path}")
        return temp_path
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete file from S3.
        
        Args:
            s3_key: S3 object key
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            print(f"✅ Deleted from S3: {s3_key}")
            return True
            
        except ClientError as e:
            print(f"❌ S3 deletion failed: {e}")
            return False
    
    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned URL for temporary file access.
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
        
        Returns:
            Presigned URL or None if generation fails
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            print(f"✅ Generated presigned URL for: {s3_key}")
            return url
            
        except ClientError as e:
            print(f"❌ Presigned URL generation failed: {e}")
            return None
    
    def file_exists(self, s3_key: str) -> bool:
        """
        Check if file exists in S3.
        
        Args:
            s3_key: S3 object key
        
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
        except ClientError:
            return False


# Global S3 service instance
s3_service = S3Service()
