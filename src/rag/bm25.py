"""BM25 search implementation for keyword-based retrieval."""

import math
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from ..models.market import Market
from ..models.news import NewsArticle
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BM25:
    """BM25 (Best Matching 25) ranking function for document retrieval."""

    def __init__(
        self,
        documents: List[str],
        doc_ids: List[str],
        k1: float = 1.5,
        b: float = 0.75,
    ):
        """Initialize BM25 index.

        Args:
            documents: List of document texts
            doc_ids: List of document identifiers
            k1: Term frequency saturation parameter (default: 1.5)
            b: Length normalization parameter (default: 0.75)
        """
        self.k1 = k1
        self.b = b
        self.doc_ids = doc_ids
        self.documents = documents

        # Build index
        self.doc_lengths: List[int] = []
        self.doc_freqs: List[Counter] = []
        self.idf: Dict[str, float] = {}
        self.avg_doc_length: float = 0

        self._build_index()

        logger.info(
            "bm25_initialized",
            num_documents=len(documents),
            avg_doc_length=self.avg_doc_length,
            vocab_size=len(self.idf),
        )

    def _build_index(self) -> None:
        """Build BM25 index from documents."""
        # Tokenize and count terms
        for doc in self.documents:
            tokens = self._tokenize(doc)
            self.doc_lengths.append(len(tokens))
            self.doc_freqs.append(Counter(tokens))

        # Calculate average document length
        self.avg_doc_length = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0
        )

        # Calculate IDF for each term
        num_docs = len(self.documents)
        term_doc_counts = defaultdict(int)

        for doc_freq in self.doc_freqs:
            for term in doc_freq.keys():
                term_doc_counts[term] += 1

        # IDF = log((N - df + 0.5) / (df + 0.5) + 1)
        for term, doc_count in term_doc_counts.items():
            self.idf[term] = math.log(
                (num_docs - doc_count + 0.5) / (doc_count + 0.5) + 1
            )

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms.

        Args:
            text: Text to tokenize

        Returns:
            List of lowercase tokens
        """
        # Simple tokenization (can be enhanced with stemming, stopword removal)
        return [
            token.lower()
            for token in text.split()
            if len(token) > 2  # Filter very short tokens
        ]

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """Search documents using BM25 scoring.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of (doc_id, score) tuples sorted by score
        """
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        # Calculate BM25 score for each document
        scores = []
        for i, (doc_freq, doc_length) in enumerate(
            zip(self.doc_freqs, self.doc_lengths)
        ):
            score = self._calculate_score(query_tokens, doc_freq, doc_length)
            scores.append((self.doc_ids[i], score))

        # Sort by score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_k]

    def _calculate_score(
        self, query_tokens: List[str], doc_freq: Counter, doc_length: int
    ) -> float:
        """Calculate BM25 score for a document.

        Args:
            query_tokens: Tokenized query
            doc_freq: Term frequencies in document
            doc_length: Document length

        Returns:
            BM25 score
        """
        score = 0.0

        for term in query_tokens:
            if term not in doc_freq:
                continue

            # Term frequency in document
            tf = doc_freq[term]

            # IDF for term
            idf = self.idf.get(term, 0)

            # Document length normalization
            norm = 1 - self.b + self.b * (doc_length / self.avg_doc_length)

            # BM25 formula
            term_score = idf * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
            score += term_score

        return score

    def add_documents(self, new_documents: List[str], new_doc_ids: List[str]) -> None:
        """Add new documents to the index.

        Args:
            new_documents: List of new document texts
            new_doc_ids: List of new document identifiers
        """
        self.documents.extend(new_documents)
        self.doc_ids.extend(new_doc_ids)

        # Rebuild index
        self.doc_lengths = []
        self.doc_freqs = []
        self.idf = {}
        self._build_index()

        logger.info("bm25_documents_added", total_documents=len(self.documents))


class BM25Index:
    """BM25 index manager for news and markets."""

    def __init__(self):
        """Initialize BM25 indices."""
        self.news_index: BM25 = None
        self.market_index: BM25 = None
        logger.info("bm25_index_manager_initialized")

    def index_news_articles(self, articles: List[NewsArticle]) -> None:
        """Index news articles for BM25 search.

        Args:
            articles: List of NewsArticle objects
        """
        if not articles:
            return

        documents = []
        doc_ids = []

        for article in articles:
            # Combine title and description for indexing
            doc_text = f"{article.title} {article.description or ''}"
            documents.append(doc_text)
            doc_ids.append(f"news_{article.id}")

        if self.news_index is None:
            self.news_index = BM25(documents, doc_ids)
        else:
            self.news_index.add_documents(documents, doc_ids)

        logger.info("news_articles_indexed_bm25", count=len(articles))

    def index_markets(self, markets: List[Market]) -> None:
        """Index markets for BM25 search.

        Args:
            markets: List of Market objects
        """
        if not markets:
            return

        documents = []
        doc_ids = []

        for market in markets:
            # Combine question and description
            doc_text = f"{market.question} {market.description or ''}"
            documents.append(doc_text)
            doc_ids.append(f"market_{market.id}")

        if self.market_index is None:
            self.market_index = BM25(documents, doc_ids)
        else:
            self.market_index.add_documents(documents, doc_ids)

        logger.info("markets_indexed_bm25", count=len(markets))

    def search_news(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search news using BM25.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of search results with scores
        """
        if self.news_index is None:
            logger.warning("news_index_not_initialized")
            return []

        results = self.news_index.search(query, top_k)

        return [
            {
                "id": doc_id.replace("news_", ""),
                "score": score,
                "type": "news",
            }
            for doc_id, score in results
        ]

    def search_markets(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search markets using BM25.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of search results with scores
        """
        if self.market_index is None:
            logger.warning("market_index_not_initialized")
            return []

        results = self.market_index.search(query, top_k)

        return [
            {
                "id": doc_id.replace("market_", ""),
                "score": score,
                "type": "market",
            }
            for doc_id, score in results
        ]


# Global BM25 index instance
bm25_index = BM25Index()
