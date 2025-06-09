import logging
from typing import List

from src.aggregator.storage.dynamodb_storage import DynamoDBStorage
from src.schemas.news_item import NewsItem


class StorageManager:
    """
    Simple storage manager that handles news item persistence.
    Acts as a facade over the DynamoDB storage implementation.
    """

    def __init__(self, table_name: str = None):
        self.storage = DynamoDBStorage(table_name)
        self.logger = logging.getLogger(__name__)

    def store_news_items(self, news_items: List[NewsItem]) -> bool:
        """
        Store a list of news items.

        Args:
            news_items: List of NewsItem objects to store

        Returns:
            bool: True if all items stored successfully
        """
        if not news_items:
            self.logger.info("No news items to store")
            return True

        stored_count = self.storage.store_news_items(news_items)
        success = stored_count == len(news_items)

        if success:
            self.logger.info(f"Successfully stored all {len(news_items)} news items")
        else:
            self.logger.warning(
                f"Only stored {stored_count}/{len(news_items)} news items"
            )

        return success

    def store_single_item(self, news_item: NewsItem) -> bool:
        """
        Store a single news item.

        Args:
            news_item: NewsItem to store

        Returns:
            bool: True if stored successfully
        """
        return self.storage.store_news_item(news_item)

    def get_recent_news(
        self, limit: int = 50, min_relevance_score: float = None
    ) -> List[NewsItem]:
        """
        Get recent news items for display in the web dashboard.

        Args:
            limit: Maximum number of items to return
            min_relevance_score: Optional minimum relevance score filter

        Returns:
            List of NewsItem objects, most recent first
        """
        return self.storage.get_recent_news(limit, min_relevance_score)

    def get_filtered_news_for_api(
        self, min_relevance_score: float = 3.0
    ) -> List[NewsItem]:
        """
        Get filtered news items for the /retrieve API endpoint.
        This method implements the specific filtering and ranking logic required
        by the assignment's API contract.

        Args:
            min_relevance_score: Minimum relevance score to include (default: 3.0 = "moderately relevant")

        Returns:
            List of NewsItem objects, sorted by importance × recency
        """
        return self.storage.get_filtered_news(min_relevance_score)

    def filter_new_articles(self, articles: List[NewsItem]) -> List[NewsItem]:
        """
        Filter out articles that already exist in storage.

        Args:
            articles: List of NewsItem objects to check

        Returns:
            List of NewsItem objects that don't exist in storage
        """
        if not articles:
            return []

        try:
            # Get existing article IDs from storage
            existing_ids = self._get_existing_article_ids(
                [article.id for article in articles]
            )

            # Filter out articles that already exist
            new_articles = [
                article for article in articles if article.id not in existing_ids
            ]

            self.logger.info(
                f"Found {len(new_articles)} new articles out of {len(articles)} total"
            )
            return new_articles

        except Exception as e:
            self.logger.error(f"Error filtering new articles: {e}")
            # Return all articles as fallback - better to re-process than miss new ones
            return articles

    def _get_existing_article_ids(self, article_ids: List[str]) -> set:
        """
        Check which article IDs already exist in storage.

        Args:
            article_ids: List of article IDs to check

        Returns:
            Set of article IDs that exist in storage
        """
        existing_ids = set()

        try:
            # For simplicity, we'll do a scan and check IDs
            # In production, you might want a more efficient approach
            response = self.storage.table.scan(
                ProjectionExpression="id",
                FilterExpression="id IN ("
                + ",".join([f":id{i}" for i in range(len(article_ids))])
                + ")",
                ExpressionAttributeValues={
                    f":id{i}": article_id for i, article_id in enumerate(article_ids)
                },
            )

            for item in response.get("Items", []):
                existing_ids.add(item["id"])

        except Exception as e:
            self.logger.error(f"Error checking existing article IDs: {e}")
            # Return empty set as fallback - will re-process articles
            return set()

        return existing_ids

    def setup(self) -> bool:
        """
        Initialize storage (create tables if needed).
        Call this during application startup.

        Returns:
            bool: True if setup successful
        """
        try:
            self.storage.create_table_if_not_exists()
            self.logger.info("Storage setup completed")
            return True
        except Exception as e:
            self.logger.error(f"Storage setup failed: {e}")
            return False
