import json
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import boto3
from shared.schemas.news_item import NewsItem

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

# Environment variables
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
JSON_KEY = os.environ.get("JSON_KEY", "news-data.json")
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "7"))
MIN_RELEVANCE_SCORE = float(os.environ.get("MIN_RELEVANCE_SCORE", "3.0"))

# Initialize DynamoDB table
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for dashboard JSON generation.

    Queries recent articles and generates dashboard JSON.
    """
    try:
        logger.info("Starting dashboard update")

        # Calculate cutoff date (N days ago)
        cutoff_date = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
        cutoff_timestamp = cutoff_date.isoformat() + "Z"

        logger.info(f"Fetching articles since {cutoff_timestamp}")

        # Query GSI for recent articles
        articles = get_recent_articles(cutoff_timestamp)

        if not articles:
            logger.info("No articles found matching criteria")
            # Still generate empty JSON
            articles = []

        logger.info(f"Retrieved {len(articles)} articles for dashboard")

        # Generate JSON data
        json_data = generate_dashboard_json(articles)

        # Upload to S3
        upload_success = upload_json_to_s3(json_data)

        if upload_success:
            logger.info("Dashboard JSON updated successfully")
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Dashboard updated successfully",
                        "articles_count": len(articles),
                        "generated_at": json_data["generated_at"],
                    }
                ),
            }
        else:
            logger.error("Failed to upload JSON to S3")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Failed to upload dashboard data"}),
            }

    except Exception as e:
        logger.error(f"Error in dashboard update: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def get_recent_articles(cutoff_timestamp: str) -> List[NewsItem]:
    """
    Get recent articles from DynamoDB using GSI.

    Args:
        cutoff_timestamp: ISO timestamp to filter articles

    Returns:
        List of NewsItem objects
    """
    try:
        # Query the GSI for recent articles
        response = table.query(
            IndexName="recent-articles-index",
            KeyConditionExpression="item_type = :type AND published_at > :cutoff",
            FilterExpression="relevance_score >= :min_score",
            ExpressionAttributeValues={
                ":type": "article",
                ":cutoff": cutoff_timestamp,
                ":min_score": Decimal(str(MIN_RELEVANCE_SCORE)),
            },
            ScanIndexForward=False,  # Newest first
        )

        items = response.get("Items", [])
        logger.info(f"Retrieved {len(items)} items from DynamoDB")

        # Convert to NewsItem objects
        news_items = []
        for item in items:
            try:
                news_item = dynamodb_item_to_news_item(item)
                news_items.append(news_item)
            except Exception as e:
                logger.error(f"Error converting DynamoDB item: {e}")
                continue

        return news_items

    except Exception as e:
        logger.error(f"Error querying recent articles: {e}")
        return []


def dynamodb_item_to_news_item(item: dict) -> NewsItem:
    """
    Convert DynamoDB item to NewsItem object.

    Args:
        item: DynamoDB item dictionary

    Returns:
        NewsItem object
    """
    # Handle Decimal type for relevance_score
    if item.get("relevance_score") is not None:
        item["relevance_score"] = float(item["relevance_score"])

    return NewsItem.from_dict(item)


def generate_dashboard_json(articles: List[NewsItem]) -> dict:
    """
    Generate JSON data structure for the dashboard.

    Args:
        articles: List of NewsItem objects

    Returns:
        Dictionary with dashboard data
    """
    now = datetime.utcnow()

    # Convert articles to JSON-serializable format
    news_data = [article.to_dict() for article in articles]

    # Calculate statistics
    sources = {}
    for article in articles:
        sources[article.source] = sources.get(article.source, 0) + 1

    return {
        "generated_at": now.isoformat() + "Z",
        "total_items": len(articles),
        "filters_applied": {
            "min_relevance_score": MIN_RELEVANCE_SCORE,
            "lookback_days": LOOKBACK_DAYS,
            "exclude_synthetic": True,
        },
        "news": news_data,
    }


def upload_json_to_s3(json_data: dict) -> bool:
    """
    Upload JSON data to S3 bucket.

    Args:
        json_data: Dictionary to upload as JSON

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        json_string = json.dumps(json_data, ensure_ascii=False, separators=(",", ":"))

        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=JSON_KEY,
            Body=json_string.encode("utf-8"),
            ContentType="application/json",
            CacheControl="no-cache, max-age=300",  # 5 minutes cache
        )

        logger.info(f"Successfully uploaded JSON to s3://{S3_BUCKET_NAME}/{JSON_KEY}")
        return True

    except Exception as e:
        logger.error(f"Error uploading JSON to S3: {e}")
        return False
