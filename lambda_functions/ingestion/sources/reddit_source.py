import logging
import os
from datetime import datetime
from typing import List, Optional

# In the ZIP file, both shared/ and praw/ are at the root level
import praw
from praw.exceptions import PRAWException
from shared.schemas.news_item import NewsItem

# Relative import
from .base import BaseSource


class RedditSource(BaseSource):
    """
    Reddit source for news aggregation using PRAW.
    Fetches posts from specified subreddit.
    """

    def __init__(self, subreddit_url: str, source_name: str, post_limit: int = 50):
        """
        Initialize Reddit source.

        Args:
            subreddit_url: Reddit URL (e.g., "https://www.reddit.com/r/InfoSecNews/")
            source_name: Source identifier (e.g., "r-infosecnews")
            post_limit: Maximum number of posts to fetch
        """
        self.subreddit_url = subreddit_url
        self._source_name = source_name
        self.post_limit = post_limit
        self.logger = logging.getLogger(f"{__name__}.{source_name}")

        # Extract subreddit name from URL
        self.subreddit_name = self._extract_subreddit_name(subreddit_url)

        # Initialize PRAW client
        self.reddit = self._init_reddit_client()

    @property
    def source_name(self) -> str:
        return self._source_name

    def fetch_articles(self) -> List[NewsItem]:
        """
        Fetch articles from Reddit subreddit and convert to NewsItem objects.

        Returns:
            List of NewsItem objects, empty list on failure
        """
        try:
            self.logger.info(f"Fetching posts from r/{self.subreddit_name}")

            # Get the subreddit
            subreddit = self.reddit.subreddit(self.subreddit_name)

            # Fetch new posts (could also use .hot() or .top())
            posts = subreddit.new(limit=self.post_limit)

            articles = []
            for post in posts:
                try:
                    article = self._convert_post_to_news_item(post)
                    if article:
                        articles.append(article)
                except Exception as e:
                    self.logger.error(f"Error converting post {post.id}: {e}")
                    continue

            self.logger.info(
                f"Successfully fetched {len(articles)} articles from {self.source_name}"
            )
            return articles

        except PRAWException as e:
            self.logger.error(f"Reddit API error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching from Reddit: {e}")
            return []

    def _init_reddit_client(self) -> praw.Reddit:
        """Initialize PRAW Reddit client with credentials."""

        client_id = os.getenv("REDDIT_APP_ID")
        client_secret = os.getenv("REDDIT_APP_SECRET")

        if not client_id or not client_secret:
            raise ValueError(
                "Reddit credentials not found. Please set REDDIT_APP_ID and REDDIT_APP_SECRET in .env"
            )

        # Initialize read-only Reddit instance
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="IT-News-Aggregator/1.0 (Educational Project)",
            check_for_async=False,
        )

        self.logger.info("Reddit client initialized successfully")
        return reddit

    def _extract_subreddit_name(self, url: str) -> str:
        """
        Extract subreddit name from Reddit URL.

        Args:
            url: Reddit URL (e.g., "https://www.reddit.com/r/InfoSecNews/")

        Returns:
            Subreddit name (e.g., "InfoSecNews")
        """
        # Handle various URL formats
        if "/r/" in url:
            # Extract subreddit name after /r/
            parts = url.split("/r/")
            if len(parts) > 1:
                subreddit_part = parts[1].rstrip("/")
                return subreddit_part.split("/")[0]  # Handle paths after subreddit name

        # Fallback: assume the URL contains the subreddit name
        self.logger.warning(
            f"Could not parse subreddit from URL {url}, using 'InfoSecNews' as fallback"
        )
        return "InfoSecNews"

    def _convert_post_to_news_item(self, post) -> Optional[NewsItem]:
        """
        Convert Reddit post to NewsItem.

        Args:
            post: PRAW Submission object

        Returns:
            NewsItem or None if conversion fails
        """
        try:
            # Skip deleted or removed posts
            if post.author is None or post.removed_by_category is not None:
                return None

            # Create unique ID combining Reddit post ID with source
            article_id = f"{self._source_name}_{post.id}"

            # Use post title
            title = post.title.strip()
            if not title:
                self.logger.warning(f"Post {post.id} has no title, skipping")
                return None

            # Determine body content and link
            body = ""
            link = None

            if post.is_self:
                # Text post - use selftext as body, Reddit permalink as link
                body = post.selftext or ""
                link = f"https://reddit.com{post.permalink}"
            else:
                # Link post - use URL as link, and any selftext as body
                link = post.url
                body = post.selftext or f"Link post to: {post.url}"

            # Convert creation time
            published_at = datetime.fromtimestamp(post.created_utc)

            return NewsItem(
                id=article_id,
                source=self.source_name,
                title=title,
                body=body,
                published_at=published_at,
                link=link,
            )

        except Exception as e:
            self.logger.error(
                f"Error converting post {getattr(post, 'id', 'unknown')}: {e}"
            )
            return None

    def _clean_text(self, text: str) -> str:
        """
        Clean Reddit text content (remove markdown, excessive whitespace).

        Args:
            text: Raw text content

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Basic cleanup - could be enhanced with markdown parsing if needed
        cleaned = text.replace("\n\n", " ").replace("\n", " ")
        cleaned = " ".join(cleaned.split())  # Normalize whitespace

        return cleaned.strip()
