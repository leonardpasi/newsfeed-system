import logging
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class S3WebsiteUploader:
    """
    Handles uploading static website files to S3 and configuring static website hosting.
    """

    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.region = region
        self.logger = logging.getLogger(__name__)

        try:
            self.s3_client = boto3.client("s3", region_name=region)
            self.s3_resource = boto3.resource("s3", region_name=region)
        except NoCredentialsError:
            self.logger.error(
                "AWS credentials not found. Please configure AWS credentials."
            )
            raise

    def create_bucket_if_not_exists(self) -> bool:
        """
        Create S3 bucket if it doesn't exist and configure for static website hosting.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                self.logger.info(f"Bucket {self.bucket_name} already exists")
            except ClientError as e:
                error_code = int(e.response["Error"]["Code"])
                if error_code == 404:
                    # Bucket doesn't exist, create it
                    self.logger.info(f"Creating bucket {self.bucket_name}")

                    if self.region == "us-east-1":
                        # us-east-1 doesn't need LocationConstraint
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": self.region
                            },
                        )
                else:
                    self.logger.error(f"Error checking bucket: {e}")
                    return False

            # Configure static website hosting
            self._configure_static_website()

            # Configure public read access
            self._configure_public_access()

            return True

        except Exception as e:
            self.logger.error(f"Error creating/configuring bucket: {e}")
            return False

    def _configure_static_website(self):
        """Configure the bucket for static website hosting."""
        try:
            website_config = {
                "IndexDocument": {"Suffix": "index.html"},
                "ErrorDocument": {"Key": "error.html"},
            }

            self.s3_client.put_bucket_website(
                Bucket=self.bucket_name, WebsiteConfiguration=website_config
            )

            self.logger.info("Configured static website hosting")

        except Exception as e:
            self.logger.error(f"Error configuring static website: {e}")
            raise

    def _configure_public_access(self):
        """Configure bucket for public read access."""
        try:
            # Disable block public access
            self.s3_client.put_public_access_block(
                Bucket=self.bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": False,
                    "IgnorePublicAcls": False,
                    "BlockPublicPolicy": False,
                    "RestrictPublicBuckets": False,
                },
            )

            # Set bucket policy for public read access
            bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicReadGetObject",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{self.bucket_name}/*",
                    }
                ],
            }

            import json

            self.s3_client.put_bucket_policy(
                Bucket=self.bucket_name, Policy=json.dumps(bucket_policy)
            )

            self.logger.info("Configured public read access")

        except Exception as e:
            self.logger.error(f"Error configuring public access: {e}")
            raise

    def upload_file(
        self,
        local_path: str,
        s3_key: str,
        content_type: Optional[str] = None,
        cache_control: Optional[str] = None,
    ) -> bool:
        """
        Upload a single file to S3.

        Args:
            local_path: Local file path
            s3_key: S3 object key (path in bucket)
            content_type: MIME type (auto-detected if None)
            cache_control: Cache control header

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Auto-detect content type if not provided
            if content_type is None:
                content_type, _ = mimetypes.guess_type(local_path)
                if content_type is None:
                    content_type = "binary/octet-stream"

            # Prepare extra args
            extra_args = {"ContentType": content_type}

            if cache_control:
                extra_args["CacheControl"] = cache_control

            # Upload file
            self.s3_client.upload_file(
                local_path, self.bucket_name, s3_key, ExtraArgs=extra_args
            )

            self.logger.info(
                f"Uploaded {local_path} -> s3://{self.bucket_name}/{s3_key}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error uploading {local_path}: {e}")
            return False

    def upload_directory(
        self,
        local_dir: str,
        s3_prefix: str = "",
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        Upload an entire directory to S3.

        Args:
            local_dir: Local directory path
            s3_prefix: S3 key prefix (directory in bucket)
            exclude_patterns: List of patterns to exclude

        Returns:
            Dict mapping file paths to upload success status
        """
        results = {}
        local_path = Path(local_dir)

        if not local_path.exists():
            self.logger.error(f"Local directory does not exist: {local_dir}")
            return results

        exclude_patterns = exclude_patterns or []

        for file_path in local_path.rglob("*"):
            if file_path.is_file():
                # Check exclusion patterns
                if any(pattern in str(file_path) for pattern in exclude_patterns):
                    self.logger.debug(f"Skipping excluded file: {file_path}")
                    continue

                # Calculate relative path and S3 key
                relative_path = file_path.relative_to(local_path)
                s3_key = str(Path(s3_prefix) / relative_path).replace("\\", "/")

                # Set appropriate cache control
                cache_control = self._get_cache_control(file_path.suffix)

                # Upload file
                success = self.upload_file(
                    str(file_path), s3_key, cache_control=cache_control
                )
                results[str(file_path)] = success

        return results

    def upload_json_data(self, json_data: str, s3_key: str = "news-data.json") -> bool:
        """
        Upload JSON data directly to S3.

        Args:
            json_data: JSON string to upload
            s3_key: S3 object key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_data.encode("utf-8"),
                ContentType="application/json",
                CacheControl="no-cache, max-age=60",  # Short cache for dynamic data
            )

            self.logger.info(f"Uploaded JSON data to s3://{self.bucket_name}/{s3_key}")
            return True

        except Exception as e:
            self.logger.error(f"Error uploading JSON data: {e}")
            return False

    def _get_cache_control(self, file_extension: str) -> str:
        """
        Get appropriate cache control header based on file type.

        Args:
            file_extension: File extension (e.g., '.html', '.css')

        Returns:
            Cache control header string
        """
        # Static assets can be cached longer
        static_extensions = {
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".ico",
            ".svg",
        }

        if file_extension.lower() in static_extensions:
            return "public, max-age=86400"  # 1 day
        else:
            return "public, max-age=300"  # 5 minutes for HTML and dynamic content

    def get_website_url(self) -> str:
        """
        Get the static website URL for the bucket.

        Returns:
            Website URL string
        """
        if self.region == "us-east-1":
            return f"http://{self.bucket_name}.s3-website-us-east-1.amazonaws.com"
        else:
            return f"http://{self.bucket_name}.s3-website-{self.region}.amazonaws.com"

    def sync_website(self, local_dir: str, delete_removed: bool = False) -> bool:
        """
        Sync local website directory with S3 bucket.

        Args:
            local_dir: Local directory containing website files
            delete_removed: Whether to delete files from S3 that don't exist locally

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Upload all files
            results = self.upload_directory(local_dir)

            # Check if all uploads were successful
            failed_uploads = [path for path, success in results.items() if not success]

            if failed_uploads:
                self.logger.warning(f"Failed to upload {len(failed_uploads)} files")
                for path in failed_uploads:
                    self.logger.warning(f"  Failed: {path}")
                return False

            self.logger.info(f"Successfully synced {len(results)} files to S3")

            # Optionally delete removed files (implement if needed)
            if delete_removed:
                self.logger.info("Delete removed files not implemented yet")

            return True

        except Exception as e:
            self.logger.error(f"Error syncing website: {e}")
            return False
