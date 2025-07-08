import json
import logging
import os
from typing import Any, Dict

# In the ZIP file, both sources/ and boto3/ are at the root level
import boto3
from sources.config import SOURCE_CONFIG
from sources.reddit_source import RedditSource
from sources.rss_source import RSSSource

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize SQS client
sqs = boto3.client("sqs")
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for news ingestion.

    Expects EventBridge event with 'source' parameter.
    Fetches articles and sends them to SQS.
    """
    try:
        # Extract source from EventBridge event
        source_name = event.get("source")
        if not source_name:
            raise ValueError("No 'source' parameter found in event")

        logger.info(f"Starting ingestion for source: {source_name}")

        # Get source configuration
        if source_name not in SOURCE_CONFIG:
            raise ValueError(f"Unknown source: {source_name}")

        config = SOURCE_CONFIG[source_name]

        # Create appropriate source instance
        if config["type"] == "rss":
            source = RSSSource(feed_url=config["url"], source_name=source_name)
        elif config["type"] == "reddit":
            source = RedditSource(
                subreddit_url=config["url"],
                source_name=source_name,
                post_limit=config.get("post_limit", 50),
            )
        else:
            raise ValueError(f"Unknown source type: {config['type']}")

        # Fetch articles
        articles = source.fetch_articles()
        logger.info(f"Fetched {len(articles)} articles from {source_name}")

        # Send articles to SQS
        sent_count = 0
        for article in articles:
            try:
                message_body = json.dumps(article.to_dict())

                sqs.send_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MessageBody=message_body,
                )
                sent_count += 1

            except Exception as e:
                logger.error(f"Failed to send article {article.id} to SQS: {e}")
                continue

        logger.info(f"Successfully sent {sent_count}/{len(articles)} articles to SQS")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Ingestion completed for {source_name}",
                    "articles_fetched": len(articles),
                    "articles_sent": sent_count,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error in ingestion handler: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
