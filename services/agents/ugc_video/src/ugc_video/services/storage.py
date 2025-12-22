import boto3
from botocore.exceptions import ClientError
from datetime import timedelta
from loguru import logger
from typing import BinaryIO
import uuid
from pathlib import Path

from ..config import Settings, get_settings


class S3StorageService:
    """Service for handling S3 file uploads, downloads, and presigned URL generation."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
            region_name=self.settings.aws_region
        )
        self.bucket_name = self.settings.s3_bucket_name

    def _generate_s3_key(self, tenant_id: str, conversation_id: str, artifact_type: str, filename: str) -> str:
        """Generate S3 key following the pattern: {tenant_id}/ugc/{conversation_id}/{artifact_type}/{filename}"""
        # Ensure filename is safe
        safe_filename = Path(filename).name
        return f"{tenant_id}/ugc/{conversation_id}/{artifact_type}/{safe_filename}"

    async def upload_file(
        self,
        file_content: bytes | BinaryIO,
        tenant_id: str,
        conversation_id: str,
        artifact_type: str,
        filename: str,
        content_type: str | None = None
    ) -> str:
        """
        Upload a file to S3 and return the S3 key.
        
        Args:
            file_content: File content as bytes or file-like object
            tenant_id: Tenant identifier
            conversation_id: Conversation identifier
            artifact_type: Type of artifact (image, video, script)
            filename: Original filename
            content_type: MIME type (optional, will be inferred if not provided)
            
        Returns:
            S3 key of the uploaded file
        """
        s3_key = self._generate_s3_key(tenant_id, conversation_id, artifact_type, filename)
        
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            # If file_content is bytes, we need to wrap it
            if isinstance(file_content, bytes):
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=file_content,
                    **extra_args
                )
            else:
                self.s3_client.upload_fileobj(
                    file_content,
                    self.bucket_name,
                    s3_key,
                    ExtraArgs=extra_args
                )
            
            logger.info(f"Successfully uploaded file to S3: {s3_key}")
            return s3_key
            
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise Exception(f"Failed to upload file to S3: {str(e)}") from e

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for temporary access to an S3 object.
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise Exception(f"Failed to generate presigned URL: {str(e)}") from e

    def get_public_url(self, s3_key: str) -> str:
        """
        Generate a public URL for an S3 object (if bucket is public).
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Public URL string
        """
        return f"https://{self.bucket_name}.s3.{self.settings.aws_region}.amazonaws.com/{s3_key}"

    async def download_file(self, s3_key: str) -> bytes:
        """
        Download a file from S3.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            File content as bytes
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Error downloading file from S3: {e}")
            raise Exception(f"Failed to download file from S3: {str(e)}") from e

    async def delete_file(self, s3_key: str) -> None:
        """
        Delete a file from S3.
        
        Args:
            s3_key: S3 object key
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Successfully deleted file from S3: {s3_key}")
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            raise Exception(f"Failed to delete file from S3: {str(e)}") from e


def get_storage_service(settings: Settings | None = None) -> S3StorageService:
    """Factory function to get S3StorageService instance."""
    return S3StorageService(settings)

