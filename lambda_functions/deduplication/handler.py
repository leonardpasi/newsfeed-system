import json
import logging
import os
from typing import Any

import boto3
from deduplicator import NewsDeduplicator
from shared.schemas.news_item import NewsItem

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
sqs = boto3.client("sqs")
DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE_NAME"]
NEW_NEWS_QUEUE_URL = os.environ["NEW_NEWS_QUEUE_URL"]

# Initialize deduplicator
deduplicator = NewsDeduplicator(DYNAMODB_TABLE)


def lambda_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler for news deduplication.

    Receives messages from raw news SQS queue, checks for duplicates,
    and forwards new items to the new news queue.
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
                # Continue processing other messages
                continue

        if not news_items:
            logger.warning("No valid news items found in batch")
            return {"statusCode": 200, "body": "No valid items to process"}

        logger.info(f"Parsed {len(news_items)} news items")

        # Filter out duplicates
        new_items = deduplicator.filter_new_items(news_items)

        if not new_items:
            logger.info("No new items found after deduplication")
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "processed_items": len(news_items),
                        "new_items": 0,
                        "duplicates_filtered": len(news_items),
                    }
                ),
            }

        # Send new items to next queue
        sent_count = send_items_to_queue(new_items)

        logger.info(
            f"Successfully processed {len(news_items)} items, sent {sent_count} new items"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "processed_items": len(news_items),
                    "new_items": sent_count,
                    "duplicates_filtered": len(news_items) - len(new_items),
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error in deduplication handler: {str(e)}")
        # Let SQS retry the batch
        raise e


def send_items_to_queue(news_items: list[NewsItem]) -> int:
    """
    Send news items to the new news SQS queue.

    Args:
        news_items: List of NewsItem objects to send

    Returns:
        Number of items successfully sent
    """
    sent_count = 0

    for item in news_items:
        try:
            message_body = json.dumps(item.to_dict())

            sqs.send_message(QueueUrl=NEW_NEWS_QUEUE_URL, MessageBody=message_body)
            sent_count += 1

        except Exception as e:
            logger.error(f"Failed to send item {item.id} to SQS: {e}")
            # Continue with other items
            continue

    return sent_count
