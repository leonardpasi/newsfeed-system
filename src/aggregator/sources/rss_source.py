import hashlib
import html
import logging
import re
import time
from datetime import datetime
from typing import Optional

import feedparser
import requests
from dateutil import parser as date_parser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.aggregator.sources.base import BaseSource
from src.schemas.news_item import NewsItem


class RSSSource(BaseSource):
    """Generic RSS/Atom feed source for news aggregation."""

    def __init__(self, feed_url: str, source_name: str, timeout: int = 30):
        self.feed_url = feed_url
        self._source_name = source_name
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.{source_name}")

        # Setup session with retries (for all HTTP and HTTPS requests)
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,  # Total number of retries
            backoff_factor=1,  # Exponential backoff (1s, 2s, 4s)
            status_forcelist=[
                429,
                500,
                502,
                503,
                504,
            ],  # Retry on these HTTP status codes
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set user agent to be respectful
        self.session.headers.update(
            {"User-Agent": "IT-News-Aggregator (Educational Project)"}
        )

    @property
    def source_name(self) -> str:
        return self._source_name

    def fetch_articles(self) -> list[NewsItem]:
        """
        Fetch articles from RSS feed and convert to NewsItem objects.

        Returns:
            List of NewsItem objects, empty list on failure
        """
        try:
            self.logger.info(f"Fetching RSS feed from {self.feed_url}")

            # Fetch the RSS feed
            response = self.session.get(self.feed_url, timeout=self.timeout)
            response.raise_for_status()

            # Parse the feed
            feed = feedparser.parse(response.content)

            if feed.bozo:
                self.logger.warning(f"Feed may be malformed: {feed.bozo_exception}")

            articles = []

            for entry in feed.entries:
                try:
                    article = self._parse_entry(entry)
                    if article:
                        articles.append(article)
                except Exception as e:
                    self.logger.error(
                        f"Error parsing entry {getattr(entry, 'title', 'Unknown')}: {e}"
                    )
                    continue

            self.logger.info(
                f"Successfully fetched {len(articles)} articles from {self.source_name}"
            )
            return articles

        except requests.RequestException as e:
            self.logger.error(f"Network error fetching {self.feed_url}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching {self.feed_url}: {e}")
            return []

    def _parse_entry(self, entry) -> Optional[NewsItem]:
        """
        Parse a single RSS entry into a NewsItem.

        Args:
            entry: feedparser entry object

        Returns:
            NewsItem or None if parsing fails
        """
        try:
            # Extract title (required)
            title = getattr(entry, "title", "").strip()
            if not title:
                self.logger.warning("Entry missing title, skipping")
                return None

            # Extract and clean body content
            body = self._extract_body(entry)

            # Extract unique ID - prefer guid, fallback to link
            article_id = self._extract_id(entry)
            if not article_id:
                self.logger.warning(f"Entry '{title}' missing ID, skipping")
                return None

            # Parse publication date
            published_at = self._parse_date(entry)
            if not published_at:
                self.logger.warning(
                    f"Entry '{title}' missing/invalid date, using current time"
                )
                published_at = datetime.utcnow()

            # Extract link
            link = self._extract_link(entry)

            return NewsItem(
                id=article_id,
                source=self.source_name,
                title=title,
                body=body,
                published_at=published_at,
                link=link,
            )

        except Exception as e:
            self.logger.error(f"Error parsing entry: {e}")
            return None

    def _extract_body(self, entry) -> str:
        """Extract body content from various RSS fields."""

        # Try different content fields
        # https://www.rssboard.org/rss-specification#hrelementsOfLtitemgt
        content_fields = ["content", "dc_content", "description"]

        for field in content_fields:
            content = getattr(entry, field, None)

            if content:
                # Handle different content structures
                if isinstance(content, list):
                    content = content[0]

                if hasattr(content, "value"):
                    # feedparser content object
                    content = content.value

                if isinstance(content, str):
                    pass
                    # content = self._clean_html(content)

                return content

        return ""

    def _extract_id(self, entry) -> Optional[str]:
        """Extract unique identifier from RSS entry."""
        # Try guid first (most reliable), then link, then title-based hash
        if hasattr(entry, "guid") and entry.guid:
            return entry.guid

        link = self._extract_link(entry)
        if link:
            return link

        # Last resort: hash of title + source
        if hasattr(entry, "title") and entry.title:
            content = f"{self.source_name}:{entry.title}"
            return hashlib.md5(content.encode()).hexdigest()

        return None

    def _extract_link(self, entry) -> Optional[str]:
        """Extract link from RSS entry."""
        if hasattr(entry, "link"):
            return entry.link
        else:
            return None

    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse publication date from RSS entry."""
        date_fields = ["published", "updated", "pubDate"]

        for field in date_fields:
            date_str = getattr(entry, field, None)
            if date_str:
                try:
                    # Use dateutil for flexible parsing
                    return date_parser.parse(date_str).replace(tzinfo=None)
                except (ValueError, TypeError) as e:
                    self.logger.debug(f"Failed to parse date '{date_str}': {e}")
                    continue

        # Try feedparser's parsed date
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime.fromtimestamp(time.mktime(entry.published_parsed))
            except (ValueError, TypeError, OverflowError):
                pass

        return None

    def _clean_html(self, html_content: str) -> str:
        """
        Clean HTML content to extract plain text.
        Basic cleaning - could be enhanced with BeautifulSoup if needed.
        """
        # Remove HTML tags
        clean_text = re.sub(r"<[^>]+>", "", html_content)

        # Decode HTML entities
        clean_text = html.unescape(clean_text)

        # Clean up whitespace
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        return clean_text
