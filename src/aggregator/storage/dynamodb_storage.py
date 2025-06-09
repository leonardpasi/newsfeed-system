import logging
from datetime import datetime
from typing import List

import boto3
from botocore.exceptions import ClientError

from src.schemas.news_item import NewsItem


class DynamoDBStorage:
    """
    Simple DynamoDB storage for news items.

    Table schema:
    - Partition Key: source (string) - e.g., "tomshardware", "reddit", "synthetic"
    - Sort Key: published_at_id (string) - format: "2025-01-15T10:30:00Z#article_id"
    - GSI: published_at-index for time-based queries across all sources
    """

    def __init__(self, table_name: str, region: str):
        self.table_name = table_name
        self.logger = logging.getLogger(__name__)

        # Initialize DynamoDB resource
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(self.table_name)

    def store_news_item(self, news_item: NewsItem) -> bool:
        """
        Store a single news item in DynamoDB.

        Args:
            news_item: NewsItem to store

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create composite sort key for better querying
            sort_key = f"{news_item.published_at.isoformat()}Z#{news_item.id}"

            item = {
                "source": news_item.source,
                "published_at_id": sort_key,
                "id": news_item.id,
                "title": news_item.title,
                "body": news_item.body,
                "published_at": news_item.published_at.isoformat() + "Z",
                "link": news_item.link,
                "is_synthetic": news_item.is_synthetic,
                "relevance_score": news_item.relevance_score,
                "created_at": datetime.utcnow().isoformat() + "Z",
            }

            # Remove None values to save space
            item = {k: v for k, v in item.items() if v is not None}

            # Use condition to prevent duplicates
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(#pk) AND attribute_not_exists(#sk)",
                ExpressionAttributeNames={"#pk": "source", "#sk": "published_at_id"},
            )

            self.logger.info(f"Stored news item: {news_item.id}")
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                self.logger.info(f"News item already exists: {news_item.id}")
                return True  # Already exists, consider it success
            else:
                self.logger.error(f"Error storing news item {news_item.id}: {e}")
                return False
        except Exception as e:
            self.logger.error(f"Unexpected error storing news item {news_item.id}: {e}")
            return False

    def store_news_items(self, news_items: List[NewsItem]) -> int:
        """
        Store multiple news items using batch operations.

        Args:
            news_items: List of NewsItem objects to store

        Returns:
            int: Number of items successfully stored
        """
        if not news_items:
            return 0

        stored_count = 0

        # DynamoDB batch_writer handles batching automatically
        try:
            with self.table.batch_writer() as batch:
                for news_item in news_items:
                    try:
                        sort_key = (
                            f"{news_item.published_at.isoformat()}Z#{news_item.id}"
                        )

                        item = {
                            "source": news_item.source,
                            "published_at_id": sort_key,
                            "id": news_item.id,
                            "title": news_item.title,
                            "body": news_item.body,
                            "published_at": news_item.published_at.isoformat() + "Z",
                            "link": news_item.link,
                            "is_synthetic": news_item.is_synthetic,
                            "relevance_score": news_item.relevance_score,
                            "created_at": datetime.utcnow().isoformat() + "Z",
                        }

                        # Remove None values
                        item = {k: v for k, v in item.items() if v is not None}

                        batch.put_item(Item=item)
                        stored_count += 1

                    except Exception as e:
                        self.logger.error(
                            f"Error preparing item {news_item.id} for batch: {e}"
                        )
                        continue

            self.logger.info(f"Batch stored {stored_count} news items")
            return stored_count

        except Exception as e:
            self.logger.error(f"Error in batch storage: {e}")
            return stored_count

    def get_recent_news(
        self, limit: int = 50, min_relevance_score: float = None
    ) -> List[NewsItem]:
        """
        Get recent news items across all sources, ordered by recency.

        Args:
            limit: Maximum number of items to return
            min_relevance_score: Optional minimum relevance score filter

        Returns:
            List of NewsItem objects, most recent first
        """
        try:
            # Use GSI to query by published_at across all sources
            response = self.table.scan(
                IndexName="published_at-index",
                Limit=limit * 2,  # Get more to allow for filtering
                Select="ALL_ATTRIBUTES",
            )

            items = response.get("Items", [])

            # Convert to NewsItem objects and filter
            news_items = []
            for item in items:
                try:
                    news_item = self._item_to_news_item(item)

                    # Apply relevance filter if specified
                    if min_relevance_score is not None:
                        if (
                            news_item.relevance_score is None
                            or news_item.relevance_score < min_relevance_score
                        ):
                            continue

                    news_items.append(news_item)

                except Exception as e:
                    self.logger.error(f"Error converting item to NewsItem: {e}")
                    continue

            # Sort by published_at (most recent first) and limit
            news_items.sort(key=lambda x: x.published_at, reverse=True)
            return news_items[:limit]

        except Exception as e:
            self.logger.error(f"Error getting recent news: {e}")
            return []

    def get_filtered_news(
        self, min_relevance_score: float = 3.0, limit: int = 50
    ) -> List[NewsItem]:
        """
        Get filtered news items for the /retrieve API endpoint.
        Returns items sorted by relevance * recency.

        Args:
            min_relevance_score: Minimum relevance score to include
            limit: Maximum number of items to return

        Returns:
            List of NewsItem objects, sorted by importance
        """
        try:
            # Scan all items (in production, you'd want better indexing)
            response = self.table.scan()
            items = response.get("Items", [])

            # Convert and filter
            filtered_items = []
            for item in items:
                try:
                    news_item = self._item_to_news_item(item)

                    # Only include items with sufficient relevance score
                    if (
                        news_item.relevance_score is not None
                        and news_item.relevance_score >= min_relevance_score
                    ):
                        filtered_items.append(news_item)

                except Exception as e:
                    self.logger.error(f"Error processing item: {e}")
                    continue

            # Sort by composite score (relevance * recency factor)
            now = datetime.utcnow()

            def importance_score(item: NewsItem) -> float:
                # Recency factor: newer items get higher scores
                age_hours = (now - item.published_at).total_seconds() / 3600
                recency_factor = max(
                    0.1, 1.0 / (1.0 + age_hours / 24)
                )  # Decay over days

                return item.relevance_score * recency_factor

            filtered_items.sort(key=importance_score, reverse=True)
            return filtered_items[:limit]

        except Exception as e:
            self.logger.error(f"Error getting filtered news: {e}")
            return []

    def _item_to_news_item(self, item: dict) -> NewsItem:
        """Convert DynamoDB item to NewsItem object."""
        return NewsItem(
            id=item["id"],
            source=item["source"],
            title=item["title"],
            body=item.get("body", ""),
            published_at=datetime.fromisoformat(item["published_at"].rstrip("Z")),
            link=item.get("link"),
            is_synthetic=item.get("is_synthetic", False),
            relevance_score=item.get("relevance_score"),
        )

    def create_table_if_not_exists(self):
        """
        Create the DynamoDB table if it doesn't exist.
        This is a utility method for setup - use IaC in production.
        """
        try:
            # Check if table exists
            self.table.load()
            self.logger.info(f"Table {self.table_name} already exists")
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                # Table doesn't exist, create it
                self.logger.info(f"Creating table {self.table_name}")

                table = self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {
                            "AttributeName": "source",
                            "KeyType": "HASH",  # Partition key
                        },
                        {
                            "AttributeName": "published_at_id",
                            "KeyType": "RANGE",  # Sort key
                        },
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "source", "AttributeType": "S"},
                        {"AttributeName": "published_at_id", "AttributeType": "S"},
                        {"AttributeName": "published_at", "AttributeType": "S"},
                    ],
                    GlobalSecondaryIndexes=[
                        {
                            "IndexName": "published_at-index",
                            "KeySchema": [
                                {"AttributeName": "published_at", "KeyType": "HASH"}
                            ],
                            "Projection": {"ProjectionType": "ALL"},
                            "BillingMode": "OnDemandThroughput",
                        }
                    ],
                    BillingMode="OnDemandThroughput",  # Simpler than provisioned capacity
                )

                # Wait for table to be created
                table.wait_until_exists()
                self.logger.info(f"Table {self.table_name} created successfully")
                return True
            else:
                self.logger.error(f"Error checking/creating table: {e}")
                return False
