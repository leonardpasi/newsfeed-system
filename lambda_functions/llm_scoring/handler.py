import json
import logging
import os
from typing import Any, Dict

import boto3
from llm_filter import LLMRelevanceFilter
from shared.schemas.news_item import NewsItem

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
sqs = boto3.client("sqs")
FILTERED_NEWS_QUEUE_URL = os.environ["FILTERED_NEWS_QUEUE_URL"]
RELEVANCE_THRESHOLD = float(os.environ.get("RELEVANCE_THRESHOLD", "3.0"))

# Initialize LLM filter
llm_filter = LLMRelevanceFilter()


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for LLM scoring and filtering.

    Receives messages from new news SQS queue, scores with LLM,
    and forwards items above threshold to filtered news queue.
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

        logger.info(f"Parsed {len(news_items)} news items")

        # Score and filter items
        filtered_items = score_and_filter_items(news_items)

        if not filtered_items:
            logger.info("No items passed the relevance filter")
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "processed_items": len(news_items),
                        "filtered_items": 0,
                        "rejected_items": len(news_items),
                    }
                ),
            }

        # Send filtered items to next queue
        sent_count = send_items_to_queue(filtered_items)

        logger.info(
            f"Successfully processed {len(news_items)} items, sent {sent_count} filtered items"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "processed_items": len(news_items),
                    "filtered_items": sent_count,
                    "rejected_items": len(news_items) - len(filtered_items),
                    "threshold": RELEVANCE_THRESHOLD,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error in LLM scoring handler: {str(e)}")
        # Let SQS retry the batch
        raise e


def score_and_filter_items(news_items: list[NewsItem]) -> list[NewsItem]:
    """
    Score news items with LLM and filter by relevance threshold.

    Args:
        news_items: List of NewsItem objects to score

    Returns:
        List of NewsItem objects that passed the filter
    """
    filtered_items = []

    for item in news_items:
        try:
            # Score the item
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
                # Skip items that couldn't be scored (fail open for individual items)

        except Exception as e:
            logger.error(f"Error processing item {item.id}: {e}")
            # Continue with other items
            continue

    return filtered_items


def send_items_to_queue(news_items: list[NewsItem]) -> int:
    """
    Send filtered news items to the filtered news SQS queue.

    Args:
        news_items: List of NewsItem objects to send

    Returns:
        Number of items successfully sent
    """
    sent_count = 0

    for item in news_items:
        try:
            message_body = json.dumps(item.to_dict())

            sqs.send_message(QueueUrl=FILTERED_NEWS_QUEUE_URL, MessageBody=message_body)
            sent_count += 1

        except Exception as e:
            logger.error(f"Failed to send item {item.id} to SQS: {e}")
            continue

    return sent_count
