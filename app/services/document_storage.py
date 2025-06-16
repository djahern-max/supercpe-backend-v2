import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from app.core.config import settings
import uuid
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)


class DocumentStorageService:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            region_name=settings.do_spaces_region,
            endpoint_url=settings.do_spaces_endpoint,
            aws_access_key_id=settings.do_spaces_access_key,
            aws_secret_access_key=settings.do_spaces_secret_key,
        )
        self.bucket = settings.do_spaces_bucket

    async def upload_cpe_certificate(
        self, file: UploadFile, cpa_license_number: str
    ) -> dict:
        """Upload CPE certificate to DO Spaces"""

        try:
            # Validate file type
            allowed_extensions = [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"]
            file_extension = os.path.splitext(file.filename)[1].lower()

            if file_extension not in allowed_extensions:
                return {
                    "success": False,
                    "error": f"File type {file_extension} not allowed. Allowed: {allowed_extensions}",
                }

            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:8]
            safe_filename = (
                f"{cpa_license_number}/{timestamp}_{unique_id}_{file.filename}"
            )

            # Read file content
            await file.seek(0)
            content = await file.read()

            # Upload to Spaces
            self.client.put_object(
                Bucket=self.bucket,
                Key=safe_filename,
                Body=content,
                ContentType=file.content_type or "application/octet-stream",
                Metadata={
                    "cpa_license": cpa_license_number,
                    "original_filename": file.filename,
                    "upload_date": datetime.now().isoformat(),
                    "file_size": str(len(content)),
                },
            )

            # Generate public URL (if needed) or private presigned URL
            file_url = f"{settings.do_spaces_endpoint}/{self.bucket}/{safe_filename}"

            logger.info(
                f"Successfully uploaded {file.filename} for CPA {cpa_license_number}"
            )

            return {
                "success": True,
                "file_url": file_url,
                "filename": safe_filename,
                "original_name": file.filename,
                "size": len(content),
                "upload_date": datetime.now().isoformat(),
            }

        except ClientError as e:
            logger.error(f"AWS S3 error uploading file: {e}")
            return {"success": False, "error": f"Storage error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error uploading file: {e}")
            return {"success": False, "error": f"Upload failed: {str(e)}"}

    def list_cpa_documents(self, cpa_license_number: str) -> list:
        """List all documents for a specific CPA"""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket, Prefix=f"{cpa_license_number}/"
            )

            documents = []
            for obj in response.get("Contents", []):
                # Get object metadata
                metadata_response = self.client.head_object(
                    Bucket=self.bucket, Key=obj["Key"]
                )

                documents.append(
                    {
                        "filename": obj["Key"],
                        "original_name": metadata_response.get("Metadata", {}).get(
                            "original_filename", obj["Key"]
                        ),
                        "size": obj["Size"],
                        "upload_date": metadata_response.get("Metadata", {}).get(
                            "upload_date"
                        ),
                        "last_modified": obj["LastModified"].isoformat(),
                    }
                )

            return documents

        except ClientError as e:
            logger.error(f"Error listing documents for CPA {cpa_license_number}: {e}")
            return []

    def generate_download_url(self, filename: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for downloading a file"""
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": filename},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating download URL: {e}")
            return None
