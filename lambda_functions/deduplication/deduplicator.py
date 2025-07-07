import logging

import boto3
from botocore.exceptions import ClientError

# In the ZIP file, shared/ is at the root level
from shared.schemas.news_item import NewsItem

logger = logging.getLogger(__name__)


class NewsDeduplicator:
    def __init__(self, table_name: str):
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)

    def check_existing_ids(self, news_items: list[NewsItem]) -> set[str]:
        """
        Check which news item IDs already exist in DynamoDB.

        Args:
            news_items: List of NewsItem objects to check

        Returns:
            Set of IDs that already exist in the database
        """
        if not news_items:
            return set()

        existing_ids = set()
        item_ids = [item.id for item in news_items]

        try:
            # Use batch_get_item for efficient lookup
            # DynamoDB batch_get_item can handle up to 100 items
            for i in range(0, len(item_ids), 100):
                batch_ids = item_ids[i : i + 100]

                # Prepare batch get request
                request_items = {
                    self.table.name: {
                        "Keys": [{"id": item_id} for item_id in batch_ids],
                        "ProjectionExpression": "id",  # Only need ID for existence check
                    }
                }

                response = self.dynamodb.batch_get_item(RequestItems=request_items)

                # Extract existing IDs from response
                for item in response.get("Responses", {}).get(self.table.name, []):
                    existing_ids.add(item["id"])

                # Handle unprocessed keys (rare, but good practice)
                unprocessed = response.get("UnprocessedKeys", {})
                if unprocessed:
                    logger.warning(f"Unprocessed keys in batch get: {len(unprocessed)}")
                    # In production, you'd retry these

        except ClientError as e:
            logger.error(f"Error checking existing IDs: {e}")
            # Fail open - assume no items exist (better to have duplicates than lose news)
            return set()
        except Exception as e:
            logger.error(f"Unexpected error checking existing IDs: {e}")
            return set()

        logger.info(
            f"Found {len(existing_ids)} existing items out of {len(item_ids)} checked"
        )
        return existing_ids

    def filter_new_items(self, news_items: list[NewsItem]) -> list[NewsItem]:
        """
        Filter out news items that already exist in the database.

        Args:
            news_items: List of NewsItem objects to filter

        Returns:
            List of NewsItem objects that don't exist in the database
        """
        if not news_items:
            return []

        existing_ids = self.check_existing_ids(news_items)

        new_items = [item for item in news_items if item.id not in existing_ids]

        logger.info(f"Filtered {len(news_items)} items -> {len(new_items)} new items")
        return new_items
