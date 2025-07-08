import json
import logging
from pathlib import Path

import click
import yaml

from src.aggregator.filters.llm_filter import LLMRelevanceFilter
from src.aggregator.sources.reddit_source import RedditSource
from src.aggregator.sources.rss_source import RSSSource
from src.aggregator.storage.storage_manager import StorageManager
from src.utils.json_generator import NewsDataGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@click.command(context_settings={"show_default": True})
@click.option(
    "--src", "source_name", type=str, required=True, help="Source name from config"
)
@click.option("--store", is_flag=True, help="Store news items in DynamoDB")
@click.option(
    "--filter", "apply_filter", is_flag=True, help="Apply LLM relevance filtering"
)
@click.option(
    "--min-score", type=float, default=3.0, help="Minimum relevance score for filtering"
)
@click.option(
    "--generate-json", is_flag=True, help="Generate JSON file for web interface"
)
@click.option(
    "--json-output",
    type=str,
    default="web-interface/news-data.json",
    help="Output path for JSON file",
)
@click.option(
    "--max-items", type=int, default=50, help="Maximum items to include in JSON output"
)
@click.option("--upload-s3", is_flag=True, help="Upload JSON file to S3 bucket")
@click.option(
    "--s3-bucket",
    type=str,
    default="newsfeed-static-web-interface",
    help="S3 bucket name for web interface",
)
@click.option(
    "--dynamodb-table",
    type=str,
    default="news-items",
    help="DynamoDB table name",
)
def main(
    source_name: str,
    store: bool,
    apply_filter: bool,
    min_score: float,
    generate_json: bool,
    json_output: str,
    max_items: int,
    upload_s3: bool,
    s3_bucket: str,
    dynamodb_table: str,
):
    """
    Fetch news from RSS sources and optionally filter and store them.

    Examples:
        python main.py --src tomshardware
        python main.py --src tomshardware --store
        python main.py --src tomshardware --store --filter --min-score 3.5
        python main.py --src tomshardware --store --filter --generate-json
        python main.py --src tomshardware --store --filter --generate-json --upload-s3
    """
    logger = logging.getLogger(__name__)

    # Load source configuration
    configs_dir = Path(__file__).parents[1] / "configs/"

    with open(configs_dir / "sources_urls.yaml") as sources_urls:
        sources_urls_dict = yaml.safe_load(sources_urls)

    if source_name not in sources_urls_dict:
        raise ValueError(
            "Source name is invalid. See /configs/sources_urls.yaml for valid source names"
        )

    url = sources_urls_dict[source_name]
    aws_region = "eu-north-1"

    # Initialize components
    source = create_source(source_name, url)

    # Setup storage if needed
    storage_manager = None
    if store:
        storage_manager = StorageManager(dynamodb_table, aws_region)
        if not storage_manager.setup():
            logger.error("Failed to setup storage")
            return

    # Setup filtering if needed
    relevance_filter = None
    if apply_filter:
        relevance_filter = LLMRelevanceFilter()

    # Track if new items were added (for JSON generation decision)
    new_items_added = False

    try:
        # Fetch articles
        logger.info(f"Fetching articles from {source_name}")
        articles = source.fetch_articles()

        if not articles:
            logger.warning("No articles fetched")
            return

        logger.info(f"Fetched {len(articles)} articles")

        # Filter out articles that already exist in storage
        new_articles = articles
        if storage_manager:
            logger.info("Checking for existing articles...")
            new_articles = storage_manager.filter_new_articles(articles)

            existing_count = len(articles) - len(new_articles)
            if existing_count > 0:
                logger.info(f"Skipping {existing_count} articles that already exist")

            if not new_articles:
                logger.info("No new articles to process")
                # Still might want to generate JSON if requested
                if generate_json:
                    logger.info("Generating JSON file with existing data...")
                    json_file_path = generate_web_interface_json(
                        storage_manager, json_output, max_items, min_score
                    )

                    # Upload to S3 if requested
                    if upload_s3 and json_file_path:
                        upload_to_s3(json_file_path, s3_bucket, aws_region)
                return

        # Apply filtering only to new articles
        if relevance_filter and new_articles:
            logger.info(
                f"Applying relevance filtering to {len(new_articles)} new articles..."
            )
            filtered_articles = []

            for article in new_articles:
                score = relevance_filter.score_relevance(article)
                if score is not None:
                    article.relevance_score = score
                    if score >= min_score:
                        filtered_articles.append(article)
                else:
                    logger.warning(f"Failed to score article: {article.title}")

            logger.info(
                f"Filtered to {len(filtered_articles)} relevant articles (score >= {min_score})"
            )
            new_articles = filtered_articles

        # Store new articles
        if storage_manager and new_articles:
            logger.info("Storing new articles...")
            success = storage_manager.store_news_items(new_articles)
            if success:
                logger.info(f"Successfully stored {len(new_articles)} new articles")
                new_items_added = True
            else:
                logger.error("Failed to store some articles")

        # Update articles reference for final display
        articles = new_articles

        # Display summary
        if articles:
            logger.info(f"Processing complete. Final count: {len(articles)} articles")

            # Show top articles
            logger.info("Top articles:")
            for i, article in enumerate(articles[:5], 1):
                score_str = (
                    f" (score: {article.relevance_score:.1f})"
                    if article.relevance_score
                    else ""
                )
                logger.info(f"  {i}. {article.title[:80]}...{score_str}")
        else:
            logger.info("No articles met the criteria")

        # Generate JSON file if requested and new items were added
        if generate_json and storage_manager:
            if new_items_added or not Path(json_output).exists():
                logger.info("Generating JSON file for web interface...")
                json_file_path = generate_web_interface_json(
                    storage_manager, json_output, max_items, min_score
                )

                # Upload to S3 if requested
                if upload_s3 and json_file_path:
                    upload_to_s3(json_file_path, s3_bucket, aws_region)
            else:
                logger.info("No new items added, skipping JSON generation")

    except Exception as e:
        logger.error(f"Error processing {source_name}: {e}")
        raise


def generate_web_interface_json(
    storage_manager: StorageManager,
    output_path: str,
    max_items: int,
    min_relevance_score: float = 1.0,
) -> str:
    """
    Generate JSON file for the web interface.

    Args:
        storage_manager: StorageManager instance
        output_path: Path where to save the JSON file
        max_items: Maximum number of items to include
        min_relevance_score: Minimum relevance score to include

    Returns:
        Path to the generated JSON file
    """
    logger = logging.getLogger(__name__)

    try:
        # Initialize JSON generator
        json_generator = NewsDataGenerator(storage_manager)

        # Generate the JSON data (no sorting - users control sorting in frontend)
        json_data = json_generator.generate_web_data(
            max_items=max_items,
            min_relevance_score=min_relevance_score,
            exclude_synthetic=True,
            sort_items=False,  # Let users sort in the frontend
        )

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Generated JSON file: {output_path} ({len(json_data['news'])} items)"
        )
        return str(output_file)

    except Exception as e:
        logger.error(f"Error generating JSON file: {e}")
        raise


def upload_to_s3(json_file_path: str, bucket_name: str, region: str):
    """
    Upload the JSON file to S3 bucket.

    Args:
        json_file_path: Path to the JSON file to upload
        bucket_name: S3 bucket name
    """
    logger = logging.getLogger(__name__)

    try:
        from src.utils.s3_uploader import S3WebsiteUploader

        # Initialize S3 uploader
        uploader = S3WebsiteUploader(bucket_name, region)

        # Create bucket if it doesn't exist
        if not uploader.create_bucket_if_not_exists():
            logger.error("Failed to create/configure S3 bucket")
            return

        # Read JSON file and upload
        with open(json_file_path, encoding="utf-8") as f:
            json_data = f.read()

        success = uploader.upload_json_data(json_data, "news-data.json")

        if success:
            website_url = uploader.get_website_url()
            logger.info("JSON uploaded successfully!")
            logger.info(f"Website URL: {website_url}")
        else:
            logger.error("Failed to upload JSON to S3")

    except ImportError:
        logger.error("S3 uploader not available. Please ensure boto3 is installed.")
    except Exception as e:
        logger.error(f"Error uploading to S3: {e}")


def create_source(source_name: str, url: str):
    """
    Create appropriate source based on source name and URL.

    Args:
        source_name: Source identifier
        url: Source URL or identifier

    Returns:
        Source instance (RSSSource or RedditSource)
    """
    if source_name.startswith("r-"):
        # Reddit source
        return RedditSource(url, source_name)
    else:
        # RSS source (default)
        return RSSSource(url, source_name)


if __name__ == "__main__":
    main()
