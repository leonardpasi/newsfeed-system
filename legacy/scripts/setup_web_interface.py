#!/usr/bin/env python3
"""
Setup script for the web interface.
Creates directory structure and initializes S3 bucket.
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
@click.option("--region", type=str, default="eu-north-1", help="AWS region")
def setup_web_interface(bucket: str, region: str):
    """
    Setup the web interface infrastructure.

    This script will:
    1. Create the web-interface directory structure
    2. Create and configure the S3 bucket
    3. Provide next steps
    """
    logger = logging.getLogger(__name__)

    try:
        # Create directory structure
        logger.info("Creating directory structure...")

        web_dir = Path("web-interface")
        web_dir.mkdir(exist_ok=True)

        utils_dir = Path("src/utils")
        utils_dir.mkdir(parents=True, exist_ok=True)

        # Create __init__.py files if they don't exist
        (utils_dir / "__init__.py").touch()

        logger.info("✅ Directory structure created")

        # Initialize S3 bucket
        logger.info(f"Setting up S3 bucket: {bucket}")

        uploader = S3WebsiteUploader(bucket, region)

        if uploader.create_bucket_if_not_exists():
            website_url = uploader.get_website_url()
            logger.info("✅ S3 bucket configured successfully!")
            logger.info(f"🌐 Website URL: {website_url}")
        else:
            logger.error("❌ Failed to configure S3 bucket")
            sys.exit(1)

        # Print next steps
        print("\n" + "=" * 60)
        print("🎉 WEB INTERFACE SETUP COMPLETE!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Place your index.html in the web-interface/ directory")
        print("2. Test your news aggregation:")
        print(
            "   python scripts/main.py --src tomshardware --store --filter --generate-json"
        )
        print("\n3. Deploy your website:")
        print("   python scripts/deploy_website.py --create-bucket")
        print("\n4. Upload JSON data:")
        print(
            "   python scripts/main.py --src tomshardware --store --filter --generate-json --upload-s3"
        )
        print(f"\n5. View your website: {website_url}")
        print("\n" + "=" * 60)

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_web_interface()
