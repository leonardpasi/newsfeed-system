import feedparser
import logging
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..models.news_item import NewsItem
from .base import BaseSource


class RSSSource(BaseSource):
    """Generic RSS/Atom feed source for news aggregation."""
    
    def __init__(self, feed_url: str, source_name: str, timeout: int = 30):
        self.feed_url = feed_url
        self._source_name = source_name
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.{source_name}")
        
        # Setup session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set user agent to be respectful
        self.session.headers.update({
            'User-Agent': 'IT-News-Aggregator/1.0 (Educational Project)'
        })
    
    @property
    def source_name(self) -> str:
        return self._source_name
    
    def fetch_articles(self) -> List[NewsItem]:
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
                    self.logger.error(f"Error parsing entry {getattr(entry, 'title', 'Unknown')}: {e}")
                    continue
            
            self.logger.info(f"Successfully fetched {len(articles)} articles from {self.source_name}")
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
            title = getattr(entry, 'title', '').strip()
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
                self.logger.warning(f"Entry '{title}' missing/invalid date, using current time")
                published_at = datetime.utcnow()
            
            return NewsItem(
                id=article_id,
                source=self.source_name,
                title=title,
                body=body,
                published_at=published_at
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing entry: {e}")
            return None
    
    def _extract_body(self, entry) -> str:
        """Extract body content from various RSS fields."""
        # Try different content fields in order of preference
        content_fields = [
            'content',      # Atom content
            'summary',      # RSS description/summary
            'description'   # RSS description
        ]
        
        for field in content_fields:
            content = getattr(entry, field, None)
            if content:
                # Handle different content structures
                if isinstance(content, list) and content:
                    # Atom content is often a list
                    content = content[0]
                
                if hasattr(content, 'value'):
                    # feedparser content object
                    return self._clean_html(content.value)
                elif isinstance(content, str):
                    return self._clean_html(content)
        
        return ""
    
    def _extract_id(self, entry) -> Optional[str]:
        """Extract unique identifier from RSS entry."""
        # Try guid first (most reliable), then link, then title-based hash
        if hasattr(entry, 'guid') and entry.guid:
            return entry.guid
        
        if hasattr(entry, 'id') and entry.id:
            return entry.id
            
        if hasattr(entry, 'link') and entry.link:
            return entry.link
        
        # Last resort: hash of title + source
        if hasattr(entry, 'title') and entry.title:
            import hashlib
            content = f"{self.source_name}:{entry.title}"
            return hashlib.md5(content.encode()).hexdigest()
        
        return None
    
    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse publication date from RSS entry."""
        date_fields = ['published', 'updated', 'pubDate']
        
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
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                import time
                return datetime.fromtimestamp(time.mktime(entry.published_parsed))
            except (ValueError, TypeError, OverflowError):
                pass
        
        return None
    
    def _clean_html(self, html_content: str) -> str:
        """
        Clean HTML content to extract plain text.
        Basic cleaning - could be enhanced with BeautifulSoup if needed.
        """
        import re
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        
        # Decode HTML entities
        import html
        clean_text = html.unescape(clean_text)
        
        # Clean up whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text