# test_llm_filter.py
from datetime import datetime

from dotenv import load_dotenv

from src.aggregator.filters.llm_filter import LLMRelevanceFilter
from src.schemas.news_item import NewsItem

# Load environment variables
load_dotenv()


def test_filter():
    """Test the LLM filter with sample news items."""

    filter = LLMRelevanceFilter()

    # Test cases with different relevance levels
    test_items = [
        NewsItem(
            id="test1",
            source="test",
            title="Major Security Breach at Microsoft Exposes Customer Data",
            body="Microsoft reported a significant security breach affecting millions of customers...",
            published_at=datetime.utcnow(),
        ),
        NewsItem(
            id="test2",
            source="test",
            title="New iPhone Color Released",
            body="Apple announced a new purple color option for the iPhone...",
            published_at=datetime.utcnow(),
        ),
        NewsItem(
            id="test3",
            source="test",
            title="Critical Vulnerability Found in OpenSSL",
            body="A critical remote code execution vulnerability was discovered in OpenSSL...",
            published_at=datetime.utcnow(),
        ),
    ]

    print("Testing LLM Relevance Filter:")
    print("-" * 50)

    for item in test_items:
        score = filter.score_relevance(item)
        print(f"Title: {item.title}")
        print(f"Score: {score}/5")
        print("-" * 50)


if __name__ == "__main__":
    test_filter()
