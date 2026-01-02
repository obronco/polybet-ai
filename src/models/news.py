"""News article data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class NewsSource(str, Enum):
    """News source enumeration."""

    NEWSAPI = "newsapi"
    TAVILY = "tavily"
    RSS = "rss"
    TWITTER = "twitter"
    CUSTOM = "custom"


class SentimentScore(str, Enum):
    """Sentiment classification."""

    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class NewsArticle(BaseModel):
    """News article model."""

    # Identification
    id: str = Field(..., description="Unique article identifier")
    url: HttpUrl = Field(..., description="Article URL")
    source: NewsSource = Field(..., description="Source of the article")
    source_name: str = Field(..., description="Name of the news source")

    # Content
    title: str = Field(..., description="Article title")
    description: Optional[str] = Field(None, description="Article description/summary")
    content: Optional[str] = Field(None, description="Full article content")

    # Metadata
    author: Optional[str] = Field(None, description="Article author")
    published_at: datetime = Field(..., description="Publication timestamp")
    scraped_at: datetime = Field(
        default_factory=datetime.now, description="When article was scraped"
    )

    # Categorization
    category: Optional[str] = Field(None, description="Article category")
    tags: List[str] = Field(default_factory=list, description="Article tags/keywords")
    entities: List[str] = Field(
        default_factory=list, description="Named entities extracted"
    )

    # Analysis
    sentiment: Optional[SentimentScore] = Field(None, description="Sentiment analysis")
    sentiment_score: Optional[float] = Field(
        None, description="Sentiment score (-1 to 1)", ge=-1, le=1
    )
    relevance_score: float = Field(
        default=0.0, description="Relevance to markets (0-1)", ge=0, le=1
    )

    # Embeddings
    embedding: Optional[List[float]] = Field(
        None, description="Vector embedding for RAG"
    )

    # Additional metadata
    language: str = Field(default="en", description="Article language")
    image_url: Optional[HttpUrl] = Field(None, description="Featured image URL")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @property
    def age_hours(self) -> float:
        """Calculate article age in hours."""
        # Make datetime.now() timezone-aware to match published_at
        now = (
            datetime.now(self.published_at.tzinfo)
            if self.published_at.tzinfo
            else datetime.now()
        )
        delta = now - self.published_at
        return delta.total_seconds() / 3600

    def is_recent(self, hours: int = 24) -> bool:
        """Check if article is recent (default: within 24 hours)."""
        return self.age_hours <= hours

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), HttpUrl: str},
    )


class NewsQuery(BaseModel):
    """News search query model."""

    keywords: List[str] = Field(..., description="Search keywords")
    sources: List[NewsSource] = Field(
        default_factory=lambda: [NewsSource.NEWSAPI, NewsSource.TAVILY],
        description="News sources to query",
    )
    categories: List[str] = Field(
        default_factory=list, description="Filter by categories"
    )
    languages: List[str] = Field(
        default_factory=lambda: ["en"], description="Article languages"
    )
    from_date: Optional[datetime] = Field(None, description="Start date for search")
    to_date: Optional[datetime] = Field(None, description="End date for search")
    max_results: int = Field(default=100, description="Maximum results per source")
    sort_by: str = Field(default="publishedAt", description="Sort criteria")


class NewsCluster(BaseModel):
    """Cluster of related news articles."""

    id: str = Field(..., description="Cluster identifier")
    articles: List[NewsArticle] = Field(..., description="Articles in cluster")
    main_topic: str = Field(..., description="Main topic of cluster")
    keywords: List[str] = Field(..., description="Common keywords")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Cluster creation time"
    )
    relevance_to_markets: float = Field(
        default=0.0, description="Overall relevance to markets", ge=0, le=1
    )

    @property
    def article_count(self) -> int:
        """Get number of articles in cluster."""
        return len(self.articles)

    @property
    def latest_article(self) -> Optional[NewsArticle]:
        """Get most recent article in cluster."""
        if not self.articles:
            return None
        return max(self.articles, key=lambda a: a.published_at)

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )
