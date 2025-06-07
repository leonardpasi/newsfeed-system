from abc import ABC, abstractmethod


class BaseSource(ABC):
    @abstractmethod
    def fetch_articles(self) -> List[NewsItem]:
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass