import logging
from pathlib import Path

import click
import yaml

from src.aggregator.filters.llm_filter import LLMRelevanceFilter
from src.aggregator.sources.rss_source import RSSSource
from src.aggregator.storage.storage_manager import StorageManager

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
def main(source_name: str, store: bool, apply_filter: bool, min_score: float):
    """
    Fetch news from RSS sources and optionally filter and store them.

    Examples:
        python main.py --src tomshardware
        python main.py --src tomshardware --store
        python main.py --src tomshardware --store --filter --min-score 3.5
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

    # Initialize components
    source = RSSSource(url, source_name)

    # Setup storage if needed
    storage_manager = None
    if store:
        storage_manager = StorageManager()
        if not storage_manager.setup():
            logger.error("Failed to setup storage")
            return

    # Setup filtering if needed
    relevance_filter = None
    if apply_filter:
        relevance_filter = LLMRelevanceFilter()

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

    except Exception as e:
        logger.error(f"Error processing {source_name}: {e}")
        raise


if __name__ == "__main__":
    main()
