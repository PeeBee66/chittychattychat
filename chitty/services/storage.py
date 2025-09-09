import os
import logging
from minio import Minio
from minio.error import S3Error
from datetime import timedelta
import json
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
        self.access_key = os.getenv('MINIO_ACCESS_KEY')
        self.secret_key = os.getenv('MINIO_SECRET_KEY')
        self.attachment_bucket = os.getenv('S3_BUCKET_ATTACH', 'attachments')
        self.archive_bucket = os.getenv('S3_BUCKET_ARCHIVES', 'archives')
        
        if not all([self.access_key, self.secret_key]):
            raise ValueError("MinIO credentials are required")
        
        # Initialize MinIO client (lazy connection)
        self.client = None
        self._client_initialized = False
    
    def _get_client(self):
        """Get MinIO client, initializing if needed"""
        if not self._client_initialized:
            try:
                self.client = Minio(
                    self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=False  # Use True for HTTPS
                )
                self._ensure_buckets()
                self._client_initialized = True
                logger.info(f"MinIO client initialized for {self.endpoint}")
            except Exception as e:
                logger.error(f"Failed to initialize MinIO client: {e}")
                raise
        return self.client
    
    def _ensure_buckets(self):
        """Ensure required buckets exist"""
        try:
            for bucket in [self.attachment_bucket, self.archive_bucket]:
                if not self._get_client().bucket_exists(bucket):
                    self._get_client().make_bucket(bucket)
                    logger.info(f"Created bucket: {bucket}")
        except S3Error as e:
            logger.error(f"Error creating buckets: {e}")
            raise
    
    def generate_presigned_put_url(self, object_key: str, expires: timedelta = timedelta(minutes=10)) -> str:
        """Generate presigned URL for PUT operations"""
        try:
            client = self._get_client()
            return client.presigned_put_object(
                bucket_name=self.attachment_bucket,
                object_name=object_key,
                expires=expires
            )
        except S3Error as e:
            logger.error(f"Error generating presigned PUT URL: {e}")
            raise
    
    def generate_presigned_get_url(self, object_key: str, expires: timedelta = timedelta(hours=1)) -> str:
        """Generate presigned URL for GET operations"""
        try:
            return self._get_client().presigned_get_object(
                bucket_name=self.attachment_bucket,
                object_name=object_key,
                expires=expires
            )
        except S3Error as e:
            logger.error(f"Error generating presigned GET URL: {e}")
            raise
    
    def check_object_exists(self, object_key: str, bucket: str = None) -> bool:
        """Check if object exists in bucket"""
        if bucket is None:
            bucket = self.attachment_bucket
        try:
            self._get_client().stat_object(bucket, object_key)
            return True
        except S3Error:
            return False
    
    def store_archive(self, archive_key: str, data: Dict) -> bool:
        """Store archive data as JSON"""
        try:
            json_data = json.dumps(data, indent=2, default=str)
            json_bytes = json_data.encode('utf-8')
            
            self._get_client().put_object(
                bucket_name=self.archive_bucket,
                object_name=archive_key,
                data=json_bytes,
                length=len(json_bytes),
                content_type='application/json'
            )
            return True
        except S3Error as e:
            logger.error(f"Error storing archive: {e}")
            return False
    
    def get_archive(self, archive_key: str) -> Optional[Dict]:
        """Retrieve archive data"""
        try:
            response = self._get_client().get_object(self.archive_bucket, archive_key)
            data = json.loads(response.read().decode('utf-8'))
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            logger.error(f"Error retrieving archive: {e}")
            return None
    
    def get_object_info(self, object_key: str) -> Optional[Dict]:
        """Get object metadata"""
        try:
            stat = self._get_client().stat_object(self.attachment_bucket, object_key)
            return {
                'size': stat.size,
                'content_type': stat.content_type,
                'last_modified': stat.last_modified.isoformat() if stat.last_modified else None,
                'etag': stat.etag
            }
        except S3Error:
            return None

# Global storage service instance
storage_service = StorageService()