"""Vector store for RAG (Retrieval-Augmented Generation) with hybrid search."""

from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from ..models.market import Market
from ..models.news import NewsArticle
from ..utils.config import config
from ..utils.logger import get_logger
from .bm25 import bm25_index

logger = get_logger(__name__)


class VectorStore:
    """ChromaDB vector store for semantic search."""

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "polybet",
    ):
        """Initialize vector store.

        Args:
            persist_directory: Directory to persist database
            collection_name: Name of the collection
        """
        self.persist_directory = (
            persist_directory or config.settings.chroma_persist_directory
        )
        self.collection_name = collection_name

        # Create persist directory if it doesn't exist
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.Client(
            Settings(
                persist_directory=self.persist_directory,
                anonymized_telemetry=False,
            )
        )

        # Use OpenAI embeddings
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=config.settings.openai_api_key.get_secret_value(),
            model_name="text-embedding-3-small",
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            "vector_store_initialized",
            persist_dir=self.persist_directory,
            collection=collection_name,
        )

    def add_news_articles(self, articles: List[NewsArticle]) -> int:
        """Add news articles to vector store.

        Args:
            articles: List of NewsArticle objects

        Returns:
            Number of articles added
        """
        if not articles:
            return 0

        ids = []
        documents = []
        metadatas = []

        for article in articles:
            # Create document text from article
            doc_text = f"{article.title}\n\n{article.description or ''}"

            # Create metadata
            metadata = {
                "type": "news",
                "source": article.source.value,
                "source_name": article.source_name,
                "url": str(article.url),
                "published_at": article.published_at.isoformat(),
                "category": article.category or "general",
                "title": article.title,
            }

            ids.append(f"news_{article.id}")
            documents.append(doc_text)
            metadatas.append(metadata)

        try:
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

            # Also index in BM25 for keyword search
            bm25_index.index_news_articles(articles)

            logger.info("news_articles_added", count=len(articles))
            return len(articles)

        except Exception as e:
            logger.error("add_news_error", error=str(e))
            return 0

    def add_markets(self, markets: List[Market]) -> int:
        """Add markets to vector store.

        Args:
            markets: List of Market objects

        Returns:
            Number of markets added
        """
        if not markets:
            return 0

        ids = []
        documents = []
        metadatas = []

        for market in markets:
            # Create document text from market
            doc_text = f"{market.question}\n\n{market.description or ''}"

            # Create metadata
            metadata = {
                "type": "market",
                "market_id": market.id,
                "category": market.category,
                "status": market.status.value,
                "yes_price": float(market.yes_price),
                "liquidity": float(market.liquidity),
                "volume_24h": float(market.volume_24h),
                "end_date": market.end_date.isoformat(),
                "question": market.question,
            }

            ids.append(f"market_{market.id}")
            documents.append(doc_text)
            metadatas.append(metadata)

        try:
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

            # Also index in BM25 for keyword search
            bm25_index.index_markets(markets)

            logger.info("markets_added", count=len(markets))
            return len(markets)

        except Exception as e:
            logger.error("add_markets_error", error=str(e))
            return 0

    def search_similar_markets(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """Search for markets similar to query.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of similar markets with metadata
        """
        try:
            # Build where filter
            where = {"type": "market"}
            if filters:
                where.update(filters)

            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where,
            )

            similar_markets = []
            if results["ids"] and results["ids"][0]:
                for i, market_id in enumerate(results["ids"][0]):
                    similar_markets.append(
                        {
                            "id": market_id.replace("market_", ""),
                            "distance": results["distances"][0][i],
                            "metadata": results["metadatas"][0][i],
                            "document": results["documents"][0][i],
                        }
                    )

            logger.debug(
                "similar_markets_found",
                query=query,
                count=len(similar_markets),
            )

            return similar_markets

        except Exception as e:
            logger.error("search_markets_error", error=str(e))
            return []

    def search_relevant_news(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """Search for news articles relevant to query.

        Args:
            query: Search query (e.g., market question)
            top_k: Number of results
            filters: Optional metadata filters

        Returns:
            List of relevant news articles with metadata
        """
        try:
            # Build where filter
            where = {"type": "news"}
            if filters:
                where.update(filters)

            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where,
            )

            relevant_news = []
            if results["ids"] and results["ids"][0]:
                for i, news_id in enumerate(results["ids"][0]):
                    relevant_news.append(
                        {
                            "id": news_id.replace("news_", ""),
                            "distance": results["distances"][0][i],
                            "relevance_score": 1 - results["distances"][0][i],
                            "metadata": results["metadatas"][0][i],
                            "document": results["documents"][0][i],
                        }
                    )

            logger.debug(
                "relevant_news_found",
                query=query,
                count=len(relevant_news),
            )

            return relevant_news

        except Exception as e:
            logger.error("search_news_error", error=str(e))
            return []

    def _build_search_query(self, obj) -> str:
        """Build search query string from Market or NewsArticle.

        Args:
            obj: Market or NewsArticle object

        Returns:
            Search query string
        """
        if isinstance(obj, Market):
            return f"{obj.question} {obj.description or ''}"
        elif isinstance(obj, NewsArticle):
            return f"{obj.title} {obj.description or ''}"
        else:
            raise TypeError(f"Unsupported type for search query: {type(obj)}")

    def find_news_for_market(
        self,
        market: Market,
        top_k: int = 10,
        min_relevance: float = 0.5,
    ) -> List[Dict]:
        """Find news articles relevant to a specific market.

        Args:
            market: Market object
            top_k: Number of news articles to return
            min_relevance: Minimum relevance score (0-1)

        Returns:
            List of relevant news articles
        """
        # Build search query
        query = self._build_search_query(market)

        # Search for relevant news
        results = self.search_relevant_news(query, top_k=top_k * 2)

        # Filter by relevance threshold
        filtered_results = [r for r in results if r["relevance_score"] >= min_relevance]

        return filtered_results[:top_k]

    def find_markets_for_news(
        self,
        article: NewsArticle,
        top_k: int = 5,
        min_relevance: float = 0.5,
    ) -> List[Dict]:
        """Find markets relevant to a news article.

        Args:
            article: NewsArticle object
            top_k: Number of markets to return
            min_relevance: Minimum relevance score

        Returns:
            List of relevant markets
        """
        # Build search query
        query = self._build_search_query(article)

        # Search for similar markets
        results = self.search_similar_markets(query, top_k=top_k * 2)

        # Calculate relevance and filter
        relevant_markets = []
        for result in results:
            relevance = 1 - result["distance"]
            if relevance >= min_relevance:
                result["relevance_score"] = relevance
                relevant_markets.append(result)

        return relevant_markets[:top_k]

    def delete_old_news(self, days: int = 30) -> int:
        """Delete news articles older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of articles deleted
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            # Get all news IDs
            all_news = self.collection.get(where={"type": "news"})

            # Filter old news
            old_ids = []
            for i, metadata in enumerate(all_news["metadatas"]):
                published_at = datetime.fromisoformat(metadata["published_at"])
                if published_at < cutoff_date:
                    old_ids.append(all_news["ids"][i])

            # Delete old news
            if old_ids:
                self.collection.delete(ids=old_ids)
                logger.info("old_news_deleted", count=len(old_ids), days=days)
                return len(old_ids)

            return 0

        except Exception as e:
            logger.error("delete_old_news_error", error=str(e))
            return 0

    def get_stats(self) -> Dict:
        """Get vector store statistics.

        Returns:
            Dict with statistics
        """
        try:
            all_data = self.collection.get()

            total_count = len(all_data["ids"])
            news_count = sum(
                1 for m in all_data["metadatas"] if m.get("type") == "news"
            )
            market_count = sum(
                1 for m in all_data["metadatas"] if m.get("type") == "market"
            )

            stats = {
                "total_items": total_count,
                "news_articles": news_count,
                "markets": market_count,
                "collection_name": self.collection_name,
            }

            logger.debug("vector_store_stats", **stats)
            return stats

        except Exception as e:
            logger.error("get_stats_error", error=str(e))
            return {}

    def clear_collection(self) -> bool:
        """Clear all data from the collection.

        Returns:
            True if successful
        """
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("collection_cleared", name=self.collection_name)
            return True

        except Exception as e:
            logger.error("clear_collection_error", error=str(e))
            return False

    def _hybrid_search(
        self,
        query: str,
        search_type: str,
        top_k: int = 10,
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """Generic hybrid search combining BM25 and vector similarity.

        Args:
            query: Search query
            search_type: Type of search - "market" or "news"
            top_k: Number of results to return
            bm25_weight: Weight for BM25 scores (default: 0.3)
            vector_weight: Weight for vector similarity (default: 0.7)
            filters: Optional metadata filters

        Returns:
            List of ranked results
        """
        # Get BM25 results based on search type
        if search_type == "market":
            bm25_results = bm25_index.search_markets(query, top_k=top_k * 2)
            vector_results = self.search_similar_markets(
                query, top_k=top_k * 2, filters=filters
            )
        else:  # news
            bm25_results = bm25_index.search_news(query, top_k=top_k * 2)
            vector_results = self.search_relevant_news(
                query, top_k=top_k * 2, filters=filters
            )

        # Combine and rerank
        combined_scores = {}

        # Normalize and combine BM25 scores
        if bm25_results:
            max_bm25 = max(r["score"] for r in bm25_results) if bm25_results else 1
            for result in bm25_results:
                doc_id = result["id"]
                normalized_score = result["score"] / max_bm25 if max_bm25 > 0 else 0
                combined_scores[doc_id] = normalized_score * bm25_weight

        # Add vector similarity scores
        for result in vector_results:
            doc_id = result["id"]
            vector_score = result.get("relevance_score", 1 - result["distance"])
            if doc_id in combined_scores:
                combined_scores[doc_id] += vector_score * vector_weight
            else:
                combined_scores[doc_id] = vector_score * vector_weight

        # Sort by combined score
        ranked = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[
            :top_k
        ]

        # Get full metadata for top results
        results = []
        for doc_id, score in ranked:
            # Find result in either list to get metadata
            metadata = None
            for vr in vector_results:
                if vr["id"] == doc_id:
                    metadata = vr.get("metadata", {})
                    break

            result_dict = {
                "id": doc_id,
                "score": score,
                "hybrid_score": score,
                "metadata": metadata or {},
                "type": search_type,
            }

            # Add relevance_score for news compatibility
            if search_type == "news":
                result_dict["relevance_score"] = score

            results.append(result_dict)

        logger.debug(
            f"hybrid_search_{search_type}",
            query=query,
            bm25_results=len(bm25_results),
            vector_results=len(vector_results),
            final_results=len(results),
        )

        return results

    def hybrid_search_markets(
        self,
        query: str,
        top_k: int = 10,
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """Hybrid search combining BM25 and vector similarity for markets.

        Args:
            query: Search query
            top_k: Number of results to return
            bm25_weight: Weight for BM25 scores (default: 0.3)
            vector_weight: Weight for vector similarity (default: 0.7)
            filters: Optional metadata filters

        Returns:
            List of ranked market results
        """
        return self._hybrid_search(
            query=query,
            search_type="market",
            top_k=top_k,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            filters=filters,
        )

    def hybrid_search_news(
        self,
        query: str,
        top_k: int = 10,
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """Hybrid search combining BM25 and vector similarity for news.

        Args:
            query: Search query (e.g., market question)
            top_k: Number of results
            bm25_weight: Weight for BM25 scores (default: 0.3)
            vector_weight: Weight for vector similarity (default: 0.7)
            filters: Optional metadata filters

        Returns:
            List of ranked news results
        """
        return self._hybrid_search(
            query=query,
            search_type="news",
            top_k=top_k,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            filters=filters,
        )

    def hybrid_find_news_for_market(
        self,
        market: Market,
        top_k: int = 10,
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
    ) -> List[Dict]:
        """Find news articles for a market using hybrid search.

        Args:
            market: Market object
            top_k: Number of news articles to return
            bm25_weight: Weight for BM25 (default: 0.3)
            vector_weight: Weight for vectors (default: 0.7)

        Returns:
            List of relevant news articles with hybrid scores
        """
        query = self._build_search_query(market)

        return self.hybrid_search_news(
            query=query,
            top_k=top_k,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
        )

    def hybrid_find_markets_for_news(
        self,
        article: NewsArticle,
        top_k: int = 5,
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
    ) -> List[Dict]:
        """Find markets for a news article using hybrid search.

        Args:
            article: NewsArticle object
            top_k: Number of markets to return
            bm25_weight: Weight for BM25 (default: 0.3)
            vector_weight: Weight for vectors (default: 0.7)

        Returns:
            List of relevant markets with hybrid scores
        """
        query = self._build_search_query(article)

        return self.hybrid_search_markets(
            query=query,
            top_k=top_k,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
        )


# Global vector store instance
vector_store = VectorStore()
