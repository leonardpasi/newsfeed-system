import logging
from datetime import datetime
from typing import Dict, List

from src.aggregator.storage.storage_manager import StorageManager
from src.schemas.news_item import NewsItem


class NewsDataGenerator:
    """
    Generates JSON data for the static web interface or the /retrieve API endpoint
    Handles filtering, sorting, and formatting of news data.
    """

    def __init__(self, storage_manager: StorageManager):
        self.storage_manager = storage_manager
        self.logger = logging.getLogger(__name__)

    def generate_web_data(
        self,
        max_items: int = 50,
        min_relevance_score: float = 1.0,
        exclude_synthetic: bool = True,
        sort_items: bool = False,
    ) -> Dict:
        """
        Generate JSON data for the web interface.

        Args:
            max_items: Maximum number of items to include
            min_relevance_score: Minimum relevance score to include
            exclude_synthetic: Whether to exclude synthetic test items
            sort_items: Whether to sort by relevance×recency (False for web interface)

        Returns:
            Dictionary with news data and metadata
        """
        try:
            # Get news items from storage
            news_items = self._get_filtered_news_items(
                min_relevance_score=min_relevance_score,
                exclude_synthetic=exclude_synthetic,
            )

            # Sort only if requested (for API, not for web interface)
            if sort_items:
                sorted_items = self._sort_by_importance(news_items)
            else:
                # For web interface: sort by recency only (user will control sorting)
                sorted_items = sorted(
                    news_items, key=lambda x: x.published_at, reverse=True
                )

            # Limit to max items
            final_items = sorted_items[:max_items]

            # Convert to JSON-serializable format
            json_data = {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "total_items": len(final_items),
                "filters_applied": {
                    "min_relevance_score": min_relevance_score,
                    "exclude_synthetic": exclude_synthetic,
                    "max_items": max_items,
                },
                "news": [self._item_to_json(item) for item in final_items],
            }

            self.logger.info(
                f"Generated web data: {len(final_items)} items "
                f"(min_score: {min_relevance_score})"
            )

            return json_data

        except Exception as e:
            self.logger.error(f"Error generating web data: {e}")
            # Return empty data structure on error
            return {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "total_items": 0,
                "error": str(e),
                "news": [],
            }

    def generate_api_data(
        self, min_relevance_score: float = 1.0, include_synthetic_only: bool = True
    ) -> List[Dict]:
        """
        Generate data for the /retrieve API endpoint.
        This method is specifically for returning synthetic test data
        sorted by relevance × recency as required by the assignment.

        Args:
            min_relevance_score: Minimum relevance score to include
            include_synthetic_only: Whether to include only synthetic items (True for tests)

        Returns:
            List of news items in API format, sorted by importance
        """
        try:
            # Get filtered news items (synthetic only for API testing)
            news_items = self._get_filtered_news_items(
                min_relevance_score=min_relevance_score,
                exclude_synthetic=not include_synthetic_only,  # Invert the logic
            )

            # Sort by composite score (relevance × recency) - required for API
            sorted_items = self._sort_by_importance(news_items)

            # Convert to API format (matches assignment contract)
            api_items = [self._item_to_api_format(item) for item in sorted_items]

            self.logger.info(
                f"Generated API data: {len(api_items)} items "
                f"(min_score: {min_relevance_score}, synthetic_only: {include_synthetic_only})"
            )

            return api_items

        except Exception as e:
            self.logger.error(f"Error generating API data: {e}")
            return []

    def _get_filtered_news_items(
        self, min_relevance_score: float, exclude_synthetic: bool
    ) -> List[NewsItem]:
        """
        Get filtered news items from storage.

        Args:
            min_relevance_score: Minimum relevance score
            exclude_synthetic: Whether to exclude synthetic items

        Returns:
            List of filtered NewsItem objects
        """
        try:
            # Get recent news from storage (get more than needed for filtering)
            all_items = self.storage_manager.get_recent_news(
                limit=200,  # Get more items to allow for filtering
                min_relevance_score=None,  # We'll filter ourselves
            )
            self.logger.INFO(
                f"Retrieved {len(all_items)} items from dynamodb storage for json generation, prior to filtering."
            )

            # Apply additional filtering
            filtered_items = []
            for item in all_items:
                # Skip items without relevance scores
                if item.relevance_score is None:
                    continue

                # Apply relevance filter
                if item.relevance_score < min_relevance_score:
                    continue

                # Exclude synthetic items for production web interface
                if exclude_synthetic and item.is_synthetic:
                    continue

                filtered_items.append(item)

            return filtered_items

        except Exception as e:
            self.logger.error(f"Error filtering news items: {e}")
            return []

    def _sort_by_importance(self, items: List[NewsItem]) -> List[NewsItem]:
        """
        Sort news items by importance (relevance × recency).

        Args:
            items: List of NewsItem objects

        Returns:
            Sorted list of NewsItem objects
        """

        def importance_score(item: NewsItem) -> float:
            """Calculate composite importance score."""
            if item.relevance_score is None:
                return 0.0

            # Recency factor: newer items get higher scores
            now = datetime.utcnow()
            age_hours = (now - item.published_at).total_seconds() / 3600

            # Decay function: recent items get full weight, older items decay
            # 100% weight for items < 6 hours old
            # 50% weight for items 24 hours old
            # 10% weight for items 7 days old
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

        return sorted(items, key=importance_score, reverse=True)

    def _item_to_json(self, item: NewsItem) -> Dict:
        """
        Convert NewsItem to JSON-serializable dictionary for web interface.

        Args:
            item: NewsItem object

        Returns:
            Dictionary representation suitable for JSON
        """
        return {
            "id": item.id,
            "source": item.source,
            "title": item.title,
            "body": item.body or "",
            "published_at": item.published_at.isoformat() + "Z",
            "link": item.link,
            "relevance_score": item.relevance_score,
        }

    def _item_to_api_format(self, item: NewsItem) -> Dict:
        """
        Convert NewsItem to API format (matches assignment contract).

        Args:
            item: NewsItem object

        Returns:
            Dictionary in the exact format required by /retrieve endpoint
        """
        return {
            "id": item.id,
            "source": item.source,
            "title": item.title,
            "body": item.body or "",
            "published_at": item.published_at.isoformat() + "Z",
        }

    def generate_summary_stats(self, items: List[NewsItem]) -> Dict:
        """
        Generate summary statistics for the news items.

        Args:
            items: List of NewsItem objects

        Returns:
            Dictionary with summary statistics
        """
        if not items:
            return {
                "total_items": 0,
                "avg_relevance_score": 0.0,
                "sources": {},
                "score_distribution": {},
            }

        # Calculate statistics
        total_items = len(items)
        relevance_scores = [
            item.relevance_score for item in items if item.relevance_score
        ]
        avg_score = (
            sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
        )

        # Count by source
        sources = {}
        for item in items:
            sources[item.source] = sources.get(item.source, 0) + 1

        # Score distribution
        score_distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        for score in relevance_scores:
            score_key = str(int(score))
            if score_key in score_distribution:
                score_distribution[score_key] += 1

        return {
            "total_items": total_items,
            "avg_relevance_score": round(avg_score, 2),
            "sources": sources,
            "score_distribution": score_distribution,
        }
