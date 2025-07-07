from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NewsItem:
    """
    Simple data model for news articles.
    Matches the API contract from the assignment.
    """

    id: str
    source: str
    title: str
    body: str = ""
    published_at: datetime = None

    # Additional attributes
    link: Optional[str] = None
    is_synthetic: bool = False  # True for /ingest items, False for RSS/Reddit
    relevance_score: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        result = {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "body": self.body,
            "published_at": self.published_at.isoformat() + "Z",
        }

        # Include optional fields if they exist
        if self.link:
            result["link"] = self.link
        if self.relevance_score is not None:
            result["relevance_score"] = self.relevance_score
        if hasattr(self, "is_synthetic"):
            result["is_synthetic"] = self.is_synthetic

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "NewsItem":
        """Create from dictionary (for API ingestion)."""
        published_at = data["published_at"].rstrip("Z")

        item = cls(
            id=data["id"],
            source=data["source"],
            title=data["title"],
            body=data.get("body", ""),
            published_at=datetime.fromisoformat(published_at),
        )

        # Set optional fields
        item.link = data.get("link")
        item.relevance_score = data.get("relevance_score")
        item.is_synthetic = data.get("is_synthetic", False)

        return item
