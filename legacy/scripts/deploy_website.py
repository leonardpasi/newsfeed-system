#!/usr/bin/env python3
"""
Script to deploy the static web interface to S3.
Use this to upload HTML, CSS, and other static assets.
"""

import logging
import sys
from pathlib import Path

import click

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.s3_uploader import S3WebsiteUploader

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@click.command()
@click.option(
    "--bucket", type=str, default="newsfeed-static-web-interface", help="S3 bucket name"
)
@click.option(
    "--web-dir",
    type=str,
    default="web-interface",
    help="Local directory containing website files",
)
@click.option("--region", type=str, default="eu-north-1", help="AWS region")
@click.option("--create-bucket", is_flag=True, help="Create bucket if it doesn't exist")
def deploy_website(bucket: str, web_dir: str, region: str, create_bucket: bool):
    """
    Deploy static website files to S3.

    Examples:
        python deploy_website.py --create-bucket
        python deploy_website.py --bucket my-news-site --web-dir ./website
    """
    logger = logging.getLogger(__name__)

    try:
        # Check if web directory exists
        web_path = Path(web_dir)
        if not web_path.exists():
            logger.error(f"Web directory does not exist: {web_dir}")
            sys.exit(1)

        # Initialize S3 uploader
        logger.info(f"Initializing S3 uploader for bucket: {bucket}")
        uploader = S3WebsiteUploader(bucket, region)

        # Create bucket if requested
        if create_bucket:
            logger.info("Creating/configuring S3 bucket...")
            if not uploader.create_bucket_if_not_exists():
                logger.error("Failed to create/configure bucket")
                sys.exit(1)

        # Upload website files
        logger.info(f"Uploading website files from {web_dir}...")
        results = uploader.upload_directory(
            str(web_path), exclude_patterns=[".DS_Store", "*.pyc", "__pycache__"]
        )

        # Check results
        failed_uploads = [path for path, success in results.items() if not success]

        if failed_uploads:
            logger.error(f"Failed to upload {len(failed_uploads)} files:")
            for path in failed_uploads:
                logger.error(f"  {path}")
            sys.exit(1)

        # Success
        website_url = uploader.get_website_url()
        logger.info(f"✅ Successfully deployed {len(results)} files!")
        logger.info(f"🌐 Website URL: {website_url}")
        logger.info(f"📁 Bucket: s3://{bucket}")

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    deploy_website()
