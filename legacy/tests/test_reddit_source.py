#!/usr/bin/env python3
"""
Simple test script for Reddit source integration.
Run this to verify Reddit source is working before integrating with the main pipeline.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.aggregator.sources.reddit_source import RedditSource


def test_reddit_source():
    """Test Reddit source functionality."""
    print("🧪 Testing Reddit Source...")

    try:
        # Initialize Reddit source
        source = RedditSource(
            subreddit_url="https://www.reddit.com/r/InfoSecNews/",
            source_name="r-infosecnews",
            post_limit=10,  # Small limit for testing
        )

        print(f"✅ Reddit source initialized: {source.source_name}")

        # Fetch articles
        print("📡 Fetching articles from Reddit...")
        articles = source.fetch_articles()

        print(f"📰 Fetched {len(articles)} articles")

        # Display first few articles
        for i, article in enumerate(articles[:3], 1):
            print(f"\n--- Article {i} ---")
            print(f"ID: {article.id}")
            print(f"Title: {article.title[:80]}...")
            print(f"Source: {article.source}")
            print(f"Published: {article.published_at}")
            print(f"Link: {article.link}")
            print(
                f"Body: {article.body[:100]}..."
                if article.body
                else "Body: (no content)"
            )

        if articles:
            print(
                f"\n✅ Reddit source test successful! Found {len(articles)} articles."
            )
        else:
            print("\n⚠️ No articles found - check subreddit or credentials")

    except Exception as e:
        print(f"❌ Reddit source test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_reddit_source()
