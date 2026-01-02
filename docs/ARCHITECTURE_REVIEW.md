# 🏗️ Architecture Review: Design Principle Analysis

**Date:** 2026-01-02
**Review Type:** DRY, SRP, and Open/Closed Principle Violations
**Scope:** Full codebase (`src/` directory)

---

## 📋 Executive Summary

This review identifies violations of three fundamental design principles in the Polybet AI codebase:

- **DRY (Don't Repeat Yourself)**: 6 major violations found
- **SRP (Single Responsibility Principle)**: 6 major violations found
- **Open/Closed Principle**: 8 major violations found

**Overall Assessment:** The codebase is functional and well-structured for a prototype, but would benefit from refactoring before scaling. Most violations are concentrated in orchestration, storage, and agent classes.

---

## 🔴 DRY Violations (Don't Repeat Yourself)

### 1. ❌ Hybrid Search Logic Duplication
**Location:** `src/rag/vector_store.py:427-593`

**Problem:** `hybrid_search_markets()` and `hybrid_search_news()` contain ~90% duplicate code.

**Duplicate Code:**
```python
# Same logic appears in both methods:
# 1. Get BM25 results
# 2. Get vector results
# 3. Normalize BM25 scores
# 4. Combine weighted scores
# 5. Sort and rank
# 6. Build result dictionaries
```

**Impact:**
- 167 lines of duplicated logic
- Bug fixes must be applied twice
- Inconsistencies if one method is updated but not the other

**Recommendation:**
```python
def _hybrid_search(
    self,
    query: str,
    search_type: str,  # "market" or "news"
    top_k: int = 10,
    bm25_weight: float = 0.3,
    vector_weight: float = 0.7,
    filters: Optional[Dict] = None,
) -> List[Dict]:
    """Generic hybrid search supporting both markets and news."""
    # Single implementation used by both
    if search_type == "market":
        bm25_results = bm25_index.search_markets(query, top_k=top_k * 2)
        vector_results = self.search_similar_markets(query, top_k=top_k * 2, filters=filters)
    else:  # news
        bm25_results = bm25_index.search_news(query, top_k=top_k * 2)
        vector_results = self.search_relevant_news(query, top_k=top_k * 2, filters=filters)

    # Unified scoring logic (once)
    return self._combine_and_rank(bm25_results, vector_results, bm25_weight, vector_weight, top_k)
```

---

### 2. ❌ LLM Response Parsing Duplication
**Location:** `src/utils/llm.py:169-290`

**Problem:** `_parse_prediction_response()` and `_parse_relevance_response()` use identical parsing patterns.

**Duplicate Pattern:**
```python
# Both methods do:
for line in lines:
    if line.startswith("FIELD_NAME:"):
        value = line.split(":", 1)[1].strip()
        result["field_name"] = process(value)
```

**Recommendation:**
```python
def _parse_structured_response(
    self,
    response: str,
    field_parsers: Dict[str, Callable],
    required_fields: List[str] = None
) -> Dict[str, Any]:
    """Generic parser for colon-separated structured LLM responses."""
    result = {}
    lines = response.split("\n")

    for line in lines:
        for field_name, parser_func in field_parsers.items():
            if line.startswith(f"{field_name}:"):
                value = line.split(":", 1)[1].strip()
                result[field_name.lower()] = parser_func(value)

    if required_fields:
        self._validate_required_fields(result, required_fields)

    return result

# Usage:
def _parse_prediction_response(self, response: str) -> Dict[str, Any]:
    return self._parse_structured_response(
        response,
        field_parsers={
            "PROBABILITY": float,
            "CONFIDENCE": int,
            "REASONING": str,
            "KEY_FACTORS": lambda x: [f.strip() for f in x.split(",")]
        },
        required_fields=["probability", "confidence"]
    )
```

---

### 3. ❌ Query String Building Duplication
**Location:** `src/rag/vector_store.py` (lines 296, 325, 613, 640)

**Problem:** Same query-building pattern repeated 4 times:
```python
# Line 296
query = f"{market.question} {market.description or ''}"

# Line 325
query = f"{article.title} {article.description or ''}"

# Line 613 (identical to 296)
query = f"{market.question} {market.description or ''}"

# Line 640 (identical to 325)
query = f"{article.title} {article.description or ''}"
```

**Recommendation:**
```python
def _build_search_query(self, obj: Union[Market, NewsArticle]) -> str:
    """Build search query string from object."""
    if isinstance(obj, Market):
        return f"{obj.question} {obj.description or ''}"
    elif isinstance(obj, NewsArticle):
        return f"{obj.title} {obj.description or ''}"
    else:
        raise TypeError(f"Unsupported type: {type(obj)}")
```

---

### 4. ❌ Metadata Building Duplication
**Location:** `src/rag/vector_store.py:68-172`

**Problem:** `add_news_articles()` and `add_markets()` have identical structure:
- Create empty lists for ids, documents, metadatas
- Iterate through objects
- Build metadata dict
- Append to lists
- Add to collection
- Index in BM25

**Recommendation:**
```python
def _add_items(
    self,
    items: List[Union[NewsArticle, Market]],
    item_type: str,
    metadata_builder: Callable,
    bm25_indexer: Callable
) -> int:
    """Generic method for adding items to vector store."""
    if not items:
        return 0

    ids = []
    documents = []
    metadatas = []

    for item in items:
        doc_text, metadata = metadata_builder(item)
        ids.append(f"{item_type}_{item.id}")
        documents.append(doc_text)
        metadatas.append(metadata)

    try:
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        bm25_indexer(items)
        logger.info(f"{item_type}s_added", count=len(items))
        return len(items)
    except Exception as e:
        logger.error(f"add_{item_type}s_error", error=str(e))
        return 0
```

---

### 5. ❌ Opportunity Scoring Duplication
**Location:** `src/agents/analyst.py:305-348` and `src/agents/risk_manager.py:295-343`

**Problem:** Both implement weighted scoring with similar patterns:
- Multiple factors with weights
- Normalization using log scale
- Min/max capping
- Sum of weighted factors

**Pattern:**
```python
# analyst.py
composite_score = (
    relevance_score * relevance_weight
    + liquidity_score * liquidity_weight
    + recency_score * recency_weight
    + volume_score * volume_weight
)

# risk_manager.py
total_risk = sum(risk_factors)
# where risk_factors are weighted components
```

**Recommendation:** Create a `ScoringEngine` utility class:
```python
class WeightedScorer:
    """Utility for calculating weighted composite scores."""

    def calculate_score(
        self,
        factors: Dict[str, float],
        weights: Dict[str, float],
        normalizers: Optional[Dict[str, Callable]] = None
    ) -> float:
        """Calculate weighted score from factors."""
        score = 0.0
        for factor_name, factor_value in factors.items():
            weight = weights.get(factor_name, 0.0)

            # Apply normalization if provided
            if normalizers and factor_name in normalizers:
                factor_value = normalizers[factor_name](factor_value)

            score += factor_value * weight

        return score
```

---

### 6. ❌ Date Parsing Duplication
**Location:** `src/api/gamma.py:264-283`

**Problem:** Date parsing logic appears only once in GammaClient but is a pattern that could be reused across API clients.

**Minor Issue:** Not critical, but consider moving to a shared utility module if other API clients need similar functionality.

---

## 🟠 SRP Violations (Single Responsibility Principle)

### 1. ❌ Orchestrator Does Everything
**Location:** `src/orchestrator.py:43-229`

**Problem:** `run_trading_cycle()` has 7+ responsibilities:
1. Scrape news from multiple sources
2. Fetch active markets
3. Correlate news with markets
4. Generate predictions
5. Validate risk for each opportunity
6. Execute trades
7. Update existing positions
8. Apply exit rules
9. Check circuit breaker
10. Error handling for each step
11. Results aggregation and logging

**Impact:** 186 lines in a single method, difficult to test individual steps.

**Recommendation:** Extract to separate orchestration steps:
```python
class TradingOrchestrator:
    def __init__(self, ...):
        self.news_pipeline = NewsPipeline(self.news_scraper)
        self.opportunity_finder = OpportunityFinder(self.analyst, self.market_intel)
        self.prediction_engine = PredictionEngine(self.forecaster)
        self.trade_executor = TradeExecutor(self.trader, self.risk_manager)
        self.position_manager = PositionManager(self.trader)

    async def run_trading_cycle(self) -> Dict:
        """Orchestrate a single trading cycle."""
        news = await self.news_pipeline.fetch_recent_news()
        opportunities = await self.opportunity_finder.find_from_news(news)
        predictions = await self.prediction_engine.generate_predictions(opportunities)
        trades = await self.trade_executor.execute_approved_trades(predictions)
        closed = await self.position_manager.update_and_exit()

        return self._build_results(news, opportunities, predictions, trades, closed)
```

---

### 2. ❌ TradingAgent: Two Jobs
**Location:** `src/agents/trader.py:24-409`

**Problem:** TradingAgent does two distinct things:
1. **Trade Execution**: Execute trades (paper/real), place orders
2. **Portfolio Management**: Track balance, P&L, open positions, exit rules

**Recommendation:** Split into two classes:
```python
class TradeExecutor:
    """Handles trade execution only."""

    async def execute_trade(self, proposed_trade: ProposedTrade) -> Optional[Trade]:
        """Execute a single trade."""
        ...

    async def close_position(self, trade: Trade, exit_price: Decimal) -> Trade:
        """Close an open position."""
        ...

class PortfolioManager:
    """Manages portfolio state and positions."""

    def __init__(self, initial_balance: Decimal):
        self.portfolio = Portfolio(balance=initial_balance, ...)

    def update_position_pnl(self, markets: dict) -> None:
        """Update P&L for all open positions."""
        ...

    def apply_exit_rules(self, markets: dict) -> List[Trade]:
        """Apply stop-loss and take-profit rules."""
        ...

    def get_summary(self) -> dict:
        """Get portfolio statistics."""
        ...
```

**Usage:**
```python
class TradingAgent:
    def __init__(self, paper_trading: bool = True):
        self.executor = TradeExecutor(paper_trading)
        self.portfolio = PortfolioManager(initial_balance=10000)

    async def execute_trade(self, ...):
        trade = await self.executor.execute_trade(proposed_trade)
        if trade:
            self.portfolio.add_trade(trade)
        return trade
```

---

### 3. ❌ VectorStore: Swiss Army Knife
**Location:** `src/rag/vector_store.py:19-652`

**Problem:** VectorStore has 10+ responsibilities:
1. ChromaDB connection management
2. Embedding function configuration
3. Add news articles
4. Add markets
5. Vector similarity search
6. BM25 keyword search
7. Hybrid search orchestration
8. Data lifecycle (delete old news)
9. Statistics reporting
10. Collection management (clear, create)

**Recommendation:** Split into multiple focused classes:
```python
class VectorStoreConnection:
    """Manages ChromaDB connection and collection."""
    def __init__(self, persist_directory: str, collection_name: str):
        ...

class DocumentIndexer:
    """Handles adding documents to the vector store."""
    def add_news_articles(self, articles: List[NewsArticle]) -> int:
        ...
    def add_markets(self, markets: List[Market]) -> int:
        ...

class VectorSearchEngine:
    """Performs vector similarity searches."""
    def search_markets(self, query: str, ...) -> List[Dict]:
        ...
    def search_news(self, query: str, ...) -> List[Dict]:
        ...

class HybridSearchEngine:
    """Combines BM25 and vector search."""
    def __init__(self, vector_engine: VectorSearchEngine, bm25_index: BM25Index):
        ...
    def search(self, query: str, search_type: str, ...) -> List[Dict]:
        ...

class VectorStoreManager:
    """High-level interface combining all components."""
    def __init__(self):
        self.connection = VectorStoreConnection(...)
        self.indexer = DocumentIndexer(self.connection)
        self.vector_search = VectorSearchEngine(self.connection)
        self.hybrid_search = HybridSearchEngine(self.vector_search, bm25_index)
```

---

### 4. ❌ MarketIntelligenceAgent: Data + Analysis
**Location:** `src/agents/market_intel.py:15-338`

**Problem:** Mixes data fetching with filtering and analysis:
- API data fetching (`get_markets`, `get_market_details`)
- Market filtering (`_filter_markets`)
- Opportunity finding
- Vector indexing
- Summary generation

**Recommendation:**
```python
class MarketDataProvider:
    """Fetches market data from API."""
    def __init__(self, gamma_client: GammaClient):
        self.gamma_client = gamma_client

    async def get_markets(self, limit: int, active: bool) -> List[Market]:
        ...

class MarketFilter:
    """Filters markets based on criteria."""
    def __init__(self, filter_config: dict):
        self.config = filter_config

    def filter_markets(self, markets: List[Market]) -> List[Market]:
        ...

class MarketIntelligenceAgent:
    """High-level market intelligence interface."""
    def __init__(self):
        self.data_provider = MarketDataProvider(GammaClient())
        self.filter = MarketFilter(config.get_market_filters())

    async def get_active_markets(self, limit: int = 100) -> List[Market]:
        markets = await self.data_provider.get_markets(limit, active=True)
        return self.filter.filter_markets(markets)
```

---

### 5. ❌ NewsScraperAgent: Fetch + Filter + Index
**Location:** `src/agents/news_scraper.py:15-299`

**Problem:** Three separate concerns:
1. **Fetching**: Scrape from multiple sources
2. **Filtering**: Apply quality filters
3. **Indexing**: Store in vector database

**Recommendation:**
```python
class NewsFetcher:
    """Fetches news from aggregator."""
    def __init__(self, aggregator: NewsAggregator):
        self.aggregator = aggregator

    async def fetch(self, query: NewsQuery) -> List[NewsArticle]:
        ...

class NewsFilter:
    """Filters news articles by quality."""
    def filter_articles(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        ...

class NewsIndexer:
    """Indexes news in vector store."""
    def index(self, articles: List[NewsArticle]) -> int:
        return vector_store.add_news_articles(articles)

class NewsScraperAgent:
    """High-level news scraping interface."""
    def __init__(self):
        self.fetcher = NewsFetcher(NewsAggregator())
        self.filter = NewsFilter()
        self.indexer = NewsIndexer()

    async def scrape_news(self, lookback_hours: int = 24) -> List[NewsArticle]:
        articles = await self.fetcher.fetch(self._build_query(lookback_hours))
        filtered = self.filter.filter_articles(articles)
        self.indexer.index(filtered)
        return filtered
```

---

### 6. ❌ RiskManagerAgent: Validation + Calculation
**Location:** `src/agents/risk_manager.py:14-416`

**Problem:** Mixes trade validation with complex calculations:
1. **Validation**: Check multiple risk criteria
2. **Position Sizing**: Kelly criterion, fixed fraction
3. **Risk Scoring**: Calculate composite risk scores
4. **Circuit Breaker**: Monitor and trigger stops

**Recommendation:**
```python
class TradeValidator:
    """Validates trades against risk criteria."""
    def validate(self, prediction, market, portfolio) -> RiskAssessment:
        ...

class PositionSizer:
    """Calculates position sizes using different methods."""
    def calculate_kelly(self, prediction, portfolio) -> Decimal:
        ...
    def calculate_fixed_fraction(self, portfolio, fraction) -> Decimal:
        ...

class RiskScorer:
    """Calculates risk scores for trades."""
    def score(self, prediction, market, portfolio, size) -> float:
        ...

class CircuitBreaker:
    """Monitors portfolio and triggers stops."""
    def check(self, portfolio) -> bool:
        ...

class RiskManagerAgent:
    """High-level risk management interface."""
    def __init__(self):
        self.validator = TradeValidator(config.get_risk_limits())
        self.sizer = PositionSizer(config.get_position_sizing_config())
        self.scorer = RiskScorer()
        self.circuit_breaker = CircuitBreaker(config.get_circuit_breaker_config())
```

---

## 🟡 Open/Closed Violations

### 1. ❌ Hardcoded API Client Dependencies
**Location:** Multiple files

**Problem:** Direct instantiation prevents swapping implementations:

```python
# orchestrator.py:32
self.market_intel = MarketIntelligenceAgent()  # Can't inject mock

# market_intel.py:20
self.gamma_client = GammaClient()  # Hardcoded to Gamma API

# trader.py:51
self.polymarket_client = PolymarketClient()  # Can't use test client
```

**Impact:**
- Can't swap APIs without modifying code
- Difficult to test (need actual API)
- Can't use different providers

**Recommendation:** Use dependency injection:
```python
class AutonomousOrchestrator:
    def __init__(
        self,
        paper_trading: bool = True,
        news_scraper: Optional[NewsScraperAgent] = None,
        market_intel: Optional[MarketIntelligenceAgent] = None,
        analyst: Optional[AnalystAgent] = None,
        forecaster: Optional[ForecastingAgent] = None,
        risk_manager: Optional[RiskManagerAgent] = None,
        trader: Optional[TradingAgent] = None,
    ):
        # Inject dependencies or use defaults
        self.news_scraper = news_scraper or NewsScraperAgent()
        self.market_intel = market_intel or MarketIntelligenceAgent()
        # ...
```

**Testing:**
```python
# Now can inject mocks
mock_market_intel = MockMarketIntelligence()
orchestrator = AutonomousOrchestrator(market_intel=mock_market_intel)
```

---

### 2. ❌ Global Singleton LLM Client
**Location:** `src/utils/llm.py:294`

**Problem:** Global singleton prevents injection:
```python
# llm.py
llm_client = LLMClient()  # Global instance

# forecaster.py:9
from ..utils.llm import llm_client  # Imports global
```

**Impact:**
- Can't use different LLM providers per agent
- Can't mock for testing
- Can't have multiple configurations

**Recommendation:**
```python
# Remove global singleton, inject instead:

class ForecastingAgent:
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.7,
        llm_client: Optional[LLMClient] = None
    ):
        self.llm_client = llm_client or LLMClient(model=model, temperature=temperature)
```

---

### 3. ❌ Global Singleton Vector Store
**Location:** `src/rag/vector_store.py:651`

**Problem:** Same as LLM client:
```python
# vector_store.py
vector_store = VectorStore()  # Global instance

# Used everywhere
from ..rag.vector_store import vector_store
```

**Recommendation:** Inject vector store into agents:
```python
class AnalystAgent:
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or VectorStore()
```

---

### 4. ❌ Position Sizing Method Hardcoded
**Location:** `src/agents/risk_manager.py:168-220`

**Problem:** Adding new position sizing methods requires modifying RiskManagerAgent:
```python
def calculate_position_size(self, ...):
    method = self.position_config.get("method", "kelly_criterion")

    if method == "kelly_criterion":
        ...
    elif method == "fixed_fraction":
        ...
    else:  # fixed_amount
        ...
```

**Impact:** Violates Open/Closed - not open for extension, requires modification.

**Recommendation:** Use Strategy Pattern:
```python
class PositionSizingStrategy(ABC):
    @abstractmethod
    def calculate(self, prediction, portfolio, market, config) -> Decimal:
        pass

class KellyCriterionStrategy(PositionSizingStrategy):
    def calculate(self, prediction, portfolio, market, config) -> Decimal:
        # Kelly logic
        ...

class FixedFractionStrategy(PositionSizingStrategy):
    def calculate(self, prediction, portfolio, market, config) -> Decimal:
        # Fixed fraction logic
        ...

class PositionSizer:
    STRATEGIES = {
        "kelly_criterion": KellyCriterionStrategy,
        "fixed_fraction": FixedFractionStrategy,
        "fixed_amount": FixedAmountStrategy,
    }

    def __init__(self, config: dict):
        method = config.get("method", "kelly_criterion")
        self.strategy = self.STRATEGIES[method]()

    def calculate_size(self, prediction, portfolio, market) -> Decimal:
        return self.strategy.calculate(prediction, portfolio, market, self.config)
```

**Extension:**
```python
# Adding new strategy doesn't modify existing code
class VolatilityAdjustedStrategy(PositionSizingStrategy):
    def calculate(self, prediction, portfolio, market, config) -> Decimal:
        # New sizing logic
        ...

# Register it
PositionSizer.STRATEGIES["volatility_adjusted"] = VolatilityAdjustedStrategy
```

---

### 5. ❌ Trade Execution Mode Hardcoded
**Location:** `src/agents/trader.py:110-113`

**Problem:** Paper vs real trading using if-else:
```python
if self.paper_trading:
    trade = await self._execute_paper_trade(proposed_trade)
else:
    trade = await self._execute_real_trade(proposed_trade)
```

**Impact:** Adding new execution modes (e.g., backtesting) requires modifying TradingAgent.

**Recommendation:** Strategy Pattern:
```python
class TradeExecutionStrategy(ABC):
    @abstractmethod
    async def execute(self, proposed_trade: ProposedTrade) -> Optional[Trade]:
        pass

class PaperTradingStrategy(TradeExecutionStrategy):
    async def execute(self, proposed_trade: ProposedTrade) -> Trade:
        # Paper trading logic
        ...

class RealTradingStrategy(TradeExecutionStrategy):
    async def execute(self, proposed_trade: ProposedTrade) -> Optional[Trade]:
        # Real trading logic with Polymarket client
        ...

class BacktestingStrategy(TradeExecutionStrategy):
    async def execute(self, proposed_trade: ProposedTrade) -> Trade:
        # Backtesting with historical data
        ...

class TradingAgent:
    def __init__(self, execution_strategy: TradeExecutionStrategy):
        self.execution_strategy = execution_strategy

    async def execute_trade(self, proposed_trade: ProposedTrade) -> Optional[Trade]:
        return await self.execution_strategy.execute(proposed_trade)
```

---

### 6. ❌ Market Filtering Hardcoded
**Location:** `src/agents/market_intel.py:152-216`

**Problem:** All filtering logic in one big method. Adding new filters requires modifying `_filter_markets()`.

**Recommendation:** Filter Chain Pattern:
```python
class MarketFilter(ABC):
    @abstractmethod
    def filter(self, market: Market) -> bool:
        """Return True if market passes filter."""
        pass

class LiquidityFilter(MarketFilter):
    def __init__(self, min_liquidity: Decimal):
        self.min_liquidity = min_liquidity

    def filter(self, market: Market) -> bool:
        return market.liquidity >= self.min_liquidity

class TimeToResolutionFilter(MarketFilter):
    def __init__(self, min_hours: int, max_hours: int):
        self.min_hours = min_hours
        self.max_hours = max_hours

    def filter(self, market: Market) -> bool:
        time_to_res = market.time_to_resolution_hours
        return self.min_hours <= time_to_res <= self.max_hours

class MarketFilterChain:
    def __init__(self, filters: List[MarketFilter]):
        self.filters = filters

    def filter_markets(self, markets: List[Market]) -> List[Market]:
        """Apply all filters in sequence."""
        filtered = markets
        for filter_obj in self.filters:
            filtered = [m for m in filtered if filter_obj.filter(m)]
        return filtered

# Usage:
filter_chain = MarketFilterChain([
    LiquidityFilter(min_liquidity=Decimal("10000")),
    TimeToResolutionFilter(min_hours=24, max_hours=720),
    SpreadFilter(max_spread=Decimal("0.05")),
    CategoryFilter(allowed_categories=["Politics", "Crypto"]),
])

filtered_markets = filter_chain.filter_markets(all_markets)
```

---

### 7. ❌ News Sources Hardcoded
**Location:** `src/agents/news_scraper.py:31-35`, `src/api/news_sources.py`

**Problem:** NewsAggregator hardcodes NewsAPI and Tavily sources. Adding new sources requires modifying NewsAggregator.

**Recommendation:** Plugin Architecture:
```python
class NewsSource(ABC):
    @abstractmethod
    async def search(self, query: NewsQuery) -> List[NewsArticle]:
        pass

class NewsAPISource(NewsSource):
    async def search(self, query: NewsQuery) -> List[NewsArticle]:
        ...

class TavilySource(NewsSource):
    async def search(self, query: NewsQuery) -> List[NewsArticle]:
        ...

class RSSSource(NewsSource):
    async def search(self, query: NewsQuery) -> List[NewsArticle]:
        ...

class NewsAggregator:
    def __init__(self, sources: List[NewsSource]):
        self.sources = sources  # Inject sources

    async def search_all_sources(self, query: NewsQuery) -> List[NewsArticle]:
        all_articles = []
        for source in self.sources:
            articles = await source.search(query)
            all_articles.extend(articles)
        return all_articles

# Usage:
aggregator = NewsAggregator([
    NewsAPISource(api_key=config.settings.newsapi_key),
    TavilySource(api_key=config.settings.tavily_api_key),
    RSSSource(feeds=config.rss_feeds),
    # Easy to add: TwitterSource(), RedditSource(), etc.
])
```

---

### 8. ❌ Prompt Templates Hardcoded
**Location:** `src/utils/llm.py:128-167`

**Problem:** Prompts hardcoded in LLMClient methods. Changing prompts requires modifying LLMClient.

**Recommendation:** External Prompt Templates:
```python
# prompts/forecasting.txt
You are analyzing a prediction market...
Market Question: {question}
Current Market Odds: {current_odds:.2%}
...

class PromptTemplate:
    def __init__(self, template_path: str):
        self.template = self._load_template(template_path)

    def format(self, **kwargs) -> str:
        return self.template.format(**kwargs)

class LLMClient:
    def __init__(self, ..., prompt_templates: Optional[Dict[str, PromptTemplate]] = None):
        self.prompt_templates = prompt_templates or self._load_default_templates()

    async def predict_market_outcome(self, question, current_odds, news_context, end_date):
        prompt = self.prompt_templates["forecasting"].format(
            question=question,
            current_odds=current_odds,
            news_context=news_context,
            end_date=end_date
        )
        # ...
```

---

## 📊 Priority Matrix

| Violation | Impact | Effort | Priority |
|-----------|--------|--------|----------|
| Orchestrator SRP | High | Medium | **🔴 Critical** |
| Hardcoded Dependencies (DI) | High | High | **🔴 Critical** |
| TradingAgent SRP | High | Medium | **🟠 High** |
| VectorStore SRP | Medium | High | **🟠 High** |
| Hybrid Search DRY | Medium | Low | **🟠 High** |
| Position Sizing Open/Closed | Medium | Medium | **🟡 Medium** |
| LLM Parsing DRY | Low | Low | **🟡 Medium** |
| Trade Execution Open/Closed | Medium | Medium | **🟡 Medium** |
| Market Filtering Open/Closed | Low | Medium | **🟢 Low** |
| Query Building DRY | Low | Low | **🟢 Low** |

---

## 🎯 Recommended Refactoring Order

### Phase 1: Critical Foundation (Week 1-2)
1. **Implement Dependency Injection**
   - Add constructor parameters to all agents
   - Create factory functions for default instances
   - Update tests to inject mocks
   - **Benefit:** Enables testing, swappable implementations

2. **Split Orchestrator**
   - Extract pipeline classes (NewsPipeline, OpportunityFinder, etc.)
   - Move orchestration logic to smaller methods
   - **Benefit:** Easier to test individual steps

### Phase 2: High-Impact Refactors (Week 3-4)
3. **Split TradingAgent**
   - Create TradeExecutor and PortfolioManager
   - Update orchestrator to use both
   - **Benefit:** Clearer responsibilities

4. **Fix Hybrid Search Duplication**
   - Create generic `_hybrid_search` method
   - Update both methods to use it
   - **Benefit:** 150+ lines eliminated, single source of truth

### Phase 3: Extensibility (Week 5-6)
5. **Strategy Patterns**
   - Position sizing strategies
   - Trade execution strategies
   - **Benefit:** Easy to add new methods without modification

6. **Filter Chain Pattern**
   - Market filtering chain
   - News filtering chain
   - **Benefit:** Composable, extensible filtering

### Phase 4: Polish (Week 7-8)
7. **VectorStore Refactor**
   - Split into focused classes
   - **Benefit:** Easier to maintain and extend

8. **Minor DRY Fixes**
   - LLM parsing helper
   - Query building helper
   - **Benefit:** Cleaner code

---

## 📈 Metrics

### Current State
- **Total Lines of Code**: ~3,500
- **Average Method Length**: 25 lines
- **Longest Method**: 186 lines (orchestrator.run_trading_cycle)
- **Code Duplication**: ~8% (estimated)
- **Hardcoded Dependencies**: 15+ instances

### Target State (After Refactoring)
- **Total Lines of Code**: ~4,200 (20% increase due to abstractions)
- **Average Method Length**: 15 lines
- **Longest Method**: <50 lines
- **Code Duplication**: <3%
- **Hardcoded Dependencies**: 0

---

## ✅ Sign-Off

**Assessment:** The codebase is well-structured for a prototype but has technical debt that will hinder scaling and testing. The violations identified are common in rapid development and can be addressed systematically.

**Recommendation:** Proceed with Phase 1 refactoring (Dependency Injection + Orchestrator Split) before adding major new features. This will establish a solid foundation for future development.

**Timeline:** 8 weeks for complete refactoring (can be done incrementally)

**Risk:** Low - Most refactorings are internal changes that won't affect external behavior.

---

**Reviewer:** Claude Code
**Date:** 2026-01-02
**Branch:** `claude/polymarket-agents-setup-yL1LE`
