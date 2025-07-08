import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError
from shared.filters.llm_filter import LLMRelevanceFilter
from shared.schemas.news_item import NewsItem

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client("s3")

# Environment variables
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
S3_KEY = os.environ.get("S3_KEY", "current-batch.json")
RELEVANCE_THRESHOLD = float(os.environ.get("RELEVANCE_THRESHOLD", "3.0"))

# Initialize LLM filter
llm_filter = LLMRelevanceFilter()


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for Mock Newsfeed API.

    Handles both POST /ingest and GET /retrieve endpoints.
    """
    try:
        http_method = event.get("httpMethod")

        if http_method == "POST":
            return handle_ingest(event)
        elif http_method == "GET":
            return handle_retrieve(event)
        else:
            return {
                "statusCode": 405,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": f"Method {http_method} not allowed"}),
            }

    except Exception as e:
        logger.error(f"Unexpected error in lambda handler: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }


def handle_ingest(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /ingest endpoint.

    Processes synthetic events, applies LLM filtering, and stores to S3.
    """
    try:
        # Parse request body
        body = event.get("body", "")
        if not body:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Empty request body"}),
            }

        # Parse JSON
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid JSON in request body"}),
            }

        # Ensure data is a list
        if not isinstance(data, list):
            data = [data]

        if not data:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "No events provided"}),
            }

        logger.info(f"Processing {len(data)} synthetic events")

        # Convert to NewsItem objects
        news_items = []
        for event_data in data:
            try:
                news_item = parse_event_to_news_item(event_data)
                if news_item:
                    news_items.append(news_item)
            except Exception as e:
                logger.error(
                    f"Error parsing event {event_data.get('id', 'unknown')}: {e}"
                )
                continue

        if not news_items:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "No valid events found"}),
            }

        logger.info(f"Parsed {len(news_items)} valid news items")

        # Apply LLM filtering
        filtered_items = apply_llm_filtering(news_items)

        # Sort by relevance × recency (deterministic for testing)
        sorted_items = sort_by_importance(filtered_items)

        # Store to S3
        store_to_s3(sorted_items)

        logger.info(
            f"Successfully processed batch: {len(news_items)} total, {len(filtered_items)} passed filter"
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "message": "Events ingested successfully",
                    "total_events": len(news_items),
                    "filtered_events": len(filtered_items),
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error in ingest handler: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Failed to process events"}),
        }


def handle_retrieve(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /retrieve endpoint.

    Returns filtered events from S3 in API contract format.
    """
    try:
        # Read from S3
        filtered_events = read_from_s3()

        # Convert to API format (matching assignment contract)
        api_events = [convert_to_api_format(item) for item in filtered_events]

        logger.info(f"Retrieved {len(api_events)} filtered events")

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(api_events),
        }

    except Exception as e:
        logger.error(f"Error in retrieve handler: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Failed to retrieve events"}),
        }


def parse_event_to_news_item(event_data: Dict[str, Any]) -> NewsItem:
    """
    Parse event data into NewsItem object.

    Args:
        event_data: Raw event data from /ingest request

    Returns:
        NewsItem object

    Raises:
        ValueError: If required fields are missing
    """
    # Validate required fields according to API contract
    required_fields = ["id", "source", "title", "published_at"]
    missing_fields = [field for field in required_fields if field not in event_data]

    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")

    # Use NewsItem's from_dict method
    news_item = NewsItem.from_dict(event_data)

    # Mark as synthetic test data
    news_item.is_synthetic = True

    return news_item


def apply_llm_filtering(news_items: List[NewsItem]) -> List[NewsItem]:
    """
    Apply LLM relevance filtering to news items.

    Args:
        news_items: List of NewsItem objects to filter

    Returns:
        List of NewsItem objects that passed the filter
    """
    filtered_items = []

    for item in news_items:
        try:
            # Score the item using LLM
            score = llm_filter.score_relevance(item)

            if score is not None:
                item.relevance_score = score

                if score >= RELEVANCE_THRESHOLD:
                    filtered_items.append(item)
                    logger.info(f"Item {item.id} passed filter with score {score}")
                else:
                    logger.info(
                        f"Item {item.id} rejected with score {score} (below {RELEVANCE_THRESHOLD})"
                    )
            else:
                logger.warning(f"Failed to score item {item.id}, skipping")

        except Exception as e:
            logger.error(f"Error scoring item {item.id}: {e}")
            continue

    return filtered_items


def sort_by_importance(items: List[NewsItem]) -> List[NewsItem]:
    """
    Sort news items by relevance × recency for deterministic ordering.

    Args:
        items: List of NewsItem objects to sort

    Returns:
        Sorted list of NewsItem objects (highest importance first)
    """

    def importance_score(item: NewsItem) -> float:
        """Calculate composite importance score."""
        if item.relevance_score is None:
            return 0.0

        # Recency factor: newer items get higher scores
        now = datetime.utcnow()
        age_hours = (now - item.published_at).total_seconds() / 3600

        # Decay function for recency
        if age_hours < 6:
            recency_factor = 1.0
        elif age_hours < 24:
            recency_factor = 0.8
        elif age_hours < 72:  # 3 days
            recency_factor = 0.6
        elif age_hours < 168:  # 1 week
            recency_factor = 0.4
        else:
            recency_factor = 0.2

        return item.relevance_score * recency_factor

    return sorted(items, key=importance_score, reverse=True)


def store_to_s3(news_items: List[NewsItem]) -> None:
    """
    Store filtered news items to S3 as JSON.

    Args:
        news_items: List of NewsItem objects to store
    """
    try:
        # Convert to JSON-serializable format
        data = [item.to_dict() for item in news_items]

        # Store to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=S3_KEY,
            Body=json.dumps(data),
            ContentType="application/json",
        )

        logger.info(f"Stored {len(news_items)} items to s3://{S3_BUCKET_NAME}/{S3_KEY}")

    except Exception as e:
        logger.error(f"Error storing to S3: {e}")
        raise


def read_from_s3() -> List[NewsItem]:
    """
    Read filtered news items from S3.

    Returns:
        List of NewsItem objects
    """
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=S3_KEY)
        data = json.loads(response["Body"].read().decode("utf-8"))

        # Convert back to NewsItem objects
        news_items = [NewsItem.from_dict(item_data) for item_data in data]

        logger.info(f"Read {len(news_items)} items from s3://{S3_BUCKET_NAME}/{S3_KEY}")
        return news_items

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.info("No current batch found in S3, returning empty list")
            return []
        else:
            logger.error(f"Error reading from S3: {e}")
            raise
    except Exception as e:
        logger.error(f"Error parsing S3 data: {e}")
        raise


def convert_to_api_format(news_item: NewsItem) -> Dict[str, Any]:
    """
    Convert NewsItem to API contract format.

    Args:
        news_item: NewsItem object

    Returns:
        Dictionary in API contract format
    """
    return {
        "id": news_item.id,
        "source": news_item.source,
        "title": news_item.title,
        "body": news_item.body,
        "published_at": news_item.published_at.isoformat() + "Z",
    }
