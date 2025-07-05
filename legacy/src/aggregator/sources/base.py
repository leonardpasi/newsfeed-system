from abc import ABC, abstractmethod

from src.schemas.news_item import NewsItem


class BaseSource(ABC):
    @abstractmethod
    def fetch_articles(self) -> list[NewsItem]:
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass
