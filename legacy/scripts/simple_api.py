#!/usr/bin/env python3
"""
Simple Flask API server for Mock Newsfeed API endpoints.
Provides /ingest and /retrieve endpoints for automated testing.
Uses batch-based approach - stores current batch in memory only.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Add src to path for imports
sys.path.append(str(Path(__file__).parent))

from src.aggregator.filters.llm_filter import LLMRelevanceFilter
from src.schemas.news_item import NewsItem

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Basic rate limiting to prevent abuse
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour", "10 per minute"],
)

# Configuration
MIN_RELEVANCE_SCORE = 3.0  # Moderately relevant threshold

# Initialize LLM filter (same as production)
relevance_filter = LLMRelevanceFilter()

# In-memory storage for current batch (no DynamoDB for synthetic items)
current_batch_raw = []  # Original items from /ingest
current_batch_filtered = []  # Items that passed filtering


@app.route("/api/v1/ingest", methods=["POST"])
@limiter.limit("20 per minute")  # More restrictive for ingest
def ingest_events():
    """
    Ingest raw events from automated test harness.
    Stores current batch in memory only (no DynamoDB).
    Uses the same LLM filtering logic as production.
    """
    global current_batch_raw, current_batch_filtered

    try:
        # Validate request
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()

        # Expect array of events
        if not isinstance(data, list):
            # Single event, wrap in array
            data = [data]

        if not data:
            return jsonify({"error": "No events provided"}), 400

        logger.info(f"Processing new batch of {len(data)} events")

        # Reset current batch storage
        current_batch_raw = []
        current_batch_filtered = []

        # Validate and process events
        for event_data in data:
            try:
                # Validate required fields
                required_fields = ["id", "source", "title", "published_at"]
                missing_fields = [
                    field for field in required_fields if field not in event_data
                ]

                if missing_fields:
                    logger.warning(
                        f"Event missing required fields {missing_fields}: {event_data.get('id', 'unknown')}"
                    )
                    continue

                # Parse published_at
                published_at_str = event_data["published_at"].rstrip("Z")
                published_at = datetime.fromisoformat(published_at_str)

                # Create NewsItem (mark as synthetic for testing)
                news_item = NewsItem(
                    id=event_data["id"],
                    source=event_data["source"],
                    title=event_data["title"],
                    body=event_data.get("body", ""),
                    published_at=published_at,
                    is_synthetic=True,  # Mark as test data
                )

                # Store in raw batch
                current_batch_raw.append(news_item)

                # Apply the SAME LLM filtering as production
                relevance_score = relevance_filter.score_relevance(news_item)

                if relevance_score is not None:
                    news_item.relevance_score = relevance_score

                    # Check if it passes the filter threshold
                    if relevance_score >= MIN_RELEVANCE_SCORE:
                        current_batch_filtered.append(news_item)
                        logger.info(
                            f"Accepted event {news_item.id} with score {relevance_score}"
                        )
                    else:
                        logger.info(
                            f"Rejected event {news_item.id} with score {relevance_score} (below {MIN_RELEVANCE_SCORE})"
                        )
                else:
                    logger.warning(f"Failed to score event: {news_item.id}")

            except Exception as e:
                logger.error(
                    f"Error processing event {event_data.get('id', 'unknown')}: {e}"
                )
                continue

        # Sort filtered items by importance × recency (deterministic ranking)
        current_batch_filtered.sort(key=_calculate_importance_score, reverse=True)

        logger.info(
            f"Batch processed: {len(current_batch_raw)} total, "
            f"{len(current_batch_filtered)} passed filter"
        )

        # Return acknowledgment (matching assignment contract)
        return jsonify(
            {
                "message": "Events ingested successfully",
                "ingested_count": len(current_batch_raw),
                "filtered_count": len(current_batch_filtered),
                "total_events": len(data),
            }
        ), 200

    except Exception as e:
        logger.error(f"Error in ingest endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/retrieve", methods=["GET"])
@limiter.limit("30 per minute")
def retrieve_filtered_events():
    """
    Retrieve events from current batch that passed the filtering criteria.
    Returns items sorted by relevance × recency as required by assignment.
    Only returns items from the most recent /ingest call.
    """
    try:
        # Convert current filtered batch to API format (matching assignment contract)
        api_response = []
        for item in current_batch_filtered:
            api_response.append(
                {
                    "id": item.id,
                    "source": item.source,
                    "title": item.title,
                    "body": item.body,
                    "published_at": item.published_at.isoformat() + "Z",
                }
            )

        logger.info(f"Retrieved {len(api_response)} filtered events from current batch")

        return jsonify(api_response), 200

    except Exception as e:
        logger.error(f"Error in retrieve endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/v1/health", methods=["GET"])
def health_check():
    """Simple health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "current_batch_size": len(current_batch_raw),
            "filtered_batch_size": len(current_batch_filtered),
            "endpoints": [
                "POST /api/v1/ingest - Ingest raw events (replaces current batch)",
                "GET /api/v1/retrieve - Retrieve filtered events from current batch",
                "GET /api/v1/health - Health check",
            ],
        }
    ), 200


def _calculate_importance_score(item: NewsItem) -> float:
    """
    Calculate composite importance score for deterministic ranking.
    Same logic as production system.
    """
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


@app.errorhandler(429)
def rate_limit_handler(e):
    """Handle rate limit exceeded."""
    return jsonify(
        {
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please slow down.",
        }
    ), 429


@app.errorhandler(404)
def not_found_handler(e):
    """Handle unknown endpoints."""
    return jsonify(
        {
            "error": "Endpoint not found",
            "available_endpoints": [
                "POST /api/v1/ingest - Ingest raw events",
                "GET /api/v1/retrieve - Retrieve filtered events",
                "GET /api/v1/health - Health check",
            ],
        }
    ), 404


@app.errorhandler(500)
def internal_error_handler(e):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {e}")
    return jsonify(
        {
            "error": "Internal server error",
            "message": "Something went wrong. Please try again.",
        }
    ), 500


def main():
    """Run the Flask API server."""
    # Test LLM filter
    logger.info("Testing LLM filter...")
    test_item = NewsItem(
        id="test-health-check",
        source="test",
        title="Test security vulnerability",
        body="Testing the relevance filter",
        is_synthetic=True,
    )

    test_score = relevance_filter.score_relevance(test_item)
    if test_score is not None:
        logger.info(f"✅ LLM filter working (test score: {test_score})")
    else:
        logger.warning("⚠️ LLM filter test failed - check OpenAI API key")

    # Start the server
    logger.info("🚀 Starting Mock Newsfeed API server...")
    logger.info("📍 Endpoints:")
    logger.info(
        "  POST /api/v1/ingest   - Ingest synthetic events (replaces current batch)"
    )
    logger.info("  GET  /api/v1/retrieve - Retrieve filtered events from current batch")
    logger.info("  GET  /api/v1/health   - Health check")
    logger.info("📝 Note: Synthetic data stored in memory only (not DynamoDB)")

    # Run Flask server
    # Use host='0.0.0.0' to accept connections from any IP
    # Use debug=False for production-like behavior
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
