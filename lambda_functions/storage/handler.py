import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from shared.schemas.news_item import NewsItem

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for storing filtered news items to DynamoDB.

    Receives messages from filtered news SQS queue and batch writes to DynamoDB.
    """
    try:
        records = event.get("Records", [])
        logger.info(f"Processing {len(records)} SQS records")

        if not records:
            return {"statusCode": 200, "body": "No records to process"}

        # Parse all news items from SQS messages
        news_items = []
        for record in records:
            try:
                message_body = json.loads(record["body"])
                news_item = NewsItem.from_dict(message_body)
                news_items.append(news_item)
            except Exception as e:
                logger.error(f"Error parsing SQS message: {e}")
                continue

        if not news_items:
            logger.warning("No valid news items found in batch")
            return {"statusCode": 200, "body": "No valid items to process"}

        logger.info(f"Parsed {len(news_items)} news items for storage")

        # Store items in DynamoDB using batch write
        stored_count = batch_store_items(news_items)

        logger.info(f"Successfully stored {stored_count}/{len(news_items)} items")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "processed_items": len(news_items),
                    "stored_items": stored_count,
                    "failed_items": len(news_items) - stored_count,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error in storage handler: {str(e)}")
        # Let SQS retry the batch
        raise e


def batch_store_items(news_items: list[NewsItem]) -> int:
    """
    Store news items in DynamoDB using batch write.

    Args:
        news_items: List of NewsItem objects to store

    Returns:
        Number of items successfully stored
    """
    if not news_items:
        return 0

    try:
        # Prepare batch write items
        with table.batch_writer() as batch:
            for news_item in news_items:
                try:
                    # Convert NewsItem to DynamoDB format
                    item = convert_news_item_to_dynamo_format(news_item)
                    batch.put_item(Item=item)

                except Exception as e:
                    logger.error(
                        f"Error preparing item {news_item.id} for batch write: {e}"
                    )
                    continue

        logger.info(f"Batch write completed for {len(news_items)} items")
        return len(news_items)

    except ClientError as e:
        logger.error(f"DynamoDB batch write error: {e}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error in batch write: {e}")
        return 0


def convert_news_item_to_dynamo_format(news_item: NewsItem) -> dict:
    """
    Convert NewsItem to DynamoDB item format.

    Args:
        news_item: NewsItem object to convert

    Returns:
        Dictionary in DynamoDB format
    """
    # Build the DynamoDB item
    item = {
        "id": news_item.id,
        "source": news_item.source,
        "title": news_item.title,
        "body": news_item.body or "",
        "published_at": news_item.published_at.isoformat() + "Z",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "is_synthetic": news_item.is_synthetic,
    }

    # Add optional fields
    if news_item.link:
        item["link"] = news_item.link

    if news_item.relevance_score is not None:
        # Convert to Decimal for DynamoDB
        item["relevance_score"] = Decimal(str(news_item.relevance_score))

    return item
