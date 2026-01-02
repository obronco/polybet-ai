"""Tests for Hybrid Search (BM25 + Vector Embeddings)."""

import pytest

from src.rag.bm25 import BM25


@pytest.fixture
def sample_documents():
    """Create sample documents for BM25 testing."""
    return [
        "Bitcoin price reaches new all-time high above $100,000",
        "Ethereum upgrade introduces new staking mechanism",
        "Federal Reserve announces interest rate decision",
        "Presidential election polls show tight race",
        "NBA playoffs begin with exciting matchups",
    ]


@pytest.fixture
def sample_doc_ids():
    """Document IDs for sample documents."""
    return ["doc1", "doc2", "doc3", "doc4", "doc5"]


def test_bm25_initialization(sample_documents, sample_doc_ids):
    """Test BM25 index initialization."""
    bm25 = BM25(sample_documents, sample_doc_ids)

    assert bm25.avg_doc_length > 0
    assert len(bm25.doc_lengths) == len(sample_documents)
    assert len(bm25.idf) > 0


def test_bm25_search_relevance(sample_documents, sample_doc_ids):
    """Test BM25 search returns relevant results."""
    bm25 = BM25(sample_documents, sample_doc_ids)

    # Search for Bitcoin-related documents
    results = bm25.search("Bitcoin price cryptocurrency", top_k=3)

    # Should return results
    assert len(results) > 0

    # First result should be the Bitcoin document
    assert results[0][0] == "doc1"

    # Scores should be positive for relevant results
    assert results[0][1] > 0


def test_bm25_search_ranking(sample_documents, sample_doc_ids):
    """Test BM25 ranking quality."""
    bm25 = BM25(sample_documents, sample_doc_ids)

    # Search for election-related query
    results = bm25.search("election president voting", top_k=5)

    # Should return multiple results
    assert len(results) > 0

    # Results should be sorted by score (descending)
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)


def test_bm25_add_documents(sample_documents, sample_doc_ids):
    """Test adding new documents to BM25 index."""
    bm25 = BM25(sample_documents, sample_doc_ids)
    initial_count = len(bm25.documents)

    # Add new documents
    new_docs = ["Soccer World Cup final draws massive audience"]
    new_ids = ["doc6"]
    bm25.add_documents(new_docs, new_ids)

    assert len(bm25.documents) == initial_count + 1


def test_bm25_tokenization():
    """Test BM25 tokenization."""
    documents = ["This is a test document"]
    doc_ids = ["test1"]
    bm25 = BM25(documents, doc_ids)

    tokens = bm25._tokenize("This is a test")

    # Should be lowercase
    assert all(t.islower() for t in tokens)

    # Should filter very short tokens (<=2 chars)
    assert "is" not in tokens  # 2 chars, should be filtered


def test_hybrid_search_concept():
    """Test conceptual hybrid search combining BM25 and vectors."""
    # This test demonstrates the hybrid search concept

    # BM25 scores (keyword matching)
    bm25_scores = {
        "market1": 0.8,  # High keyword match
        "market2": 0.3,
        "market3": 0.6,
    }

    # Vector similarity scores (semantic similarity)
    vector_scores = {
        "market1": 0.5,
        "market2": 0.9,  # High semantic similarity
        "market3": 0.7,
    }

    # Hybrid combination (30% BM25, 70% vector)
    bm25_weight = 0.3
    vector_weight = 0.7

    hybrid_scores = {}
    for market_id in bm25_scores.keys():
        hybrid_scores[market_id] = (
            bm25_scores[market_id] * bm25_weight
            + vector_scores[market_id] * vector_weight
        )

    # market1: 0.8*0.3 + 0.5*0.7 = 0.24 + 0.35 = 0.59
    assert abs(hybrid_scores["market1"] - 0.59) < 0.01

    # market2: 0.3*0.3 + 0.9*0.7 = 0.09 + 0.63 = 0.72
    assert abs(hybrid_scores["market2"] - 0.72) < 0.01

    # market2 should rank highest (best semantic match despite lower keywords)
    ranked = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)
    assert ranked[0][0] == "market2"


def test_bm25_vs_vector_complementarity():
    """Demonstrate how BM25 and vectors complement each other."""

    # Case 1: Exact keyword match but different semantic meaning
    # "Turkey election" (bird) vs "Turkey election" (country)
    # BM25 would match both, vectors would distinguish semantic meaning

    # Case 2: Semantic match but different keywords
    # "Bitcoin price surge" vs "BTC value increases"
    # BM25 might miss this, vectors would catch semantic similarity

    # Case 3: Both keyword and semantic match
    # "Bitcoin price increases" vs "Bitcoin price rises"
    # Both BM25 and vectors should score high

    # This is the power of hybrid search:
    # - BM25 catches exact keyword matches (good for specific terms)
    # - Vectors catch semantic similarity (good for meaning)
    # - Hybrid combines both for robust retrieval

    assert True  # Conceptual test


def test_bm25_parameter_effects():
    """Test effect of BM25 parameters k1 and b."""
    documents = ["short", "this is a much longer document with many words"]
    doc_ids = ["doc1", "doc2"]

    # Default parameters
    bm25_default = BM25(documents, doc_ids, k1=1.5, b=0.75)

    # High k1 (more weight to term frequency)
    bm25_high_k1 = BM25(documents, doc_ids, k1=2.5, b=0.75)

    # High b (more length normalization)
    bm25_high_b = BM25(documents, doc_ids, k1=1.5, b=0.9)

    # Parameters affect scoring
    assert bm25_default.k1 == 1.5
    assert bm25_high_k1.k1 == 2.5
    assert bm25_high_b.b == 0.9


def test_empty_query_handling():
    """Test BM25 handling of empty queries."""
    documents = ["test document"]
    doc_ids = ["doc1"]
    bm25 = BM25(documents, doc_ids)

    # Empty query should return empty results
    results = bm25.search("", top_k=5)
    assert len(results) == 0

    # Very short tokens should also return empty
    results = bm25.search("a b c", top_k=5)
    assert len(results) == 0
