import logging
import os
import re
from typing import Optional

from openai import OpenAI
from shared.schemas.news_item import NewsItem


class LLMRelevanceFilter:
    """
    Simple LLM-based relevance filter using OpenAI API.
    Scores news items from 1-5 based on relevance to IT managers.
    """

    def __init__(self, model: str = "gpt-4.1-nano-2025-04-14"):
        self.model = model
        self.logger = logging.getLogger(__name__)

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key is None:
            self.logger.error("OpenAI API key not found.")
            raise ValueError("OpenAI API key not found in environment variables")

        self.client = OpenAI(api_key=api_key)

    def score_relevance(self, news_item: NewsItem) -> Optional[float]:
        """
        Score a news item's relevance to IT managers (1-5 scale).

        Args:
            news_item: NewsItem to score

        Returns:
            float: Relevance score (1.0-5.0), None when scoring fails
        """
        try:
            prompt = self._build_prompt(news_item)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at evaluating IT news relevance.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=10,
                temperature=0,  # Low temperature for consistent scoring
            )

            score_text = response.choices[0].message.content.strip()
            score = self._parse_score(score_text)

            self.logger.info(f"Scored '{news_item.title[:50]}...' as {score}")
            return score

        except Exception as e:
            self.logger.error(f"Error scoring news item {news_item.id}: {e}")
            return None

    def _build_prompt(self, news_item: NewsItem) -> str:
        """Build the prompt for LLM scoring."""
        # Truncate content to save on API costs
        title = news_item.title[:200]
        body = news_item.body[:800] if news_item.body else ""

        return f"""Rate this news item's relevance to IT managers on a scale of 1-5:

1 = Not relevant (consumer tech, general business news)
2 = Slightly relevant (minor updates, product announcements)
3 = Moderately relevant (software releases, industry trends)
4 = Highly relevant (security vulnerabilities, major outages)
5 = Critical (major security breaches, widespread outages, critical bugs)

Title: {title}
Content: {body}

Consider: Does this affect IT infrastructure, security, operations, or require immediate attention?

Respond with only a number from 1 to 5."""

    def _parse_score(self, score_text: str) -> float:
        """Parse the LLM response to extract a numeric score."""
        # Extract first number found in the response

        # Look for numbers 1-5
        match = re.search(r"[1-5]", score_text)
        if match:
            return float(match.group())

        # Fallback parsing for decimal scores
        match = re.search(r"(\d+\.?\d*)", score_text)
        if match:
            score = float(match.group())
            # Clamp to 1-5 range
            return max(1.0, min(5.0, score))

        self.logger.warning(
            f"Could not parse score from: '{score_text}', defaulting to None"
        )
        return None
