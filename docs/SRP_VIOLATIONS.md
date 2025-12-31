# Single Responsibility Principle (SRP) Violations Report

## Overview

This document identifies violations of the Single Responsibility Principle in the Polybet AI codebase. SRP states that a class should have **only one reason to change** - it should have only one well-defined responsibility.

---

## Critical Violations (High Priority)

### 1. ❌ `VectorStore` (src/rag/vector_store.py) - **651 lines, 14+ methods**

**Current Responsibilities** (Multiple reasons to change):
1. ChromaDB client management
2. BM25 index management
3. News article indexing
4. Market indexing
5. Vector search for markets
6. Vector search for news
7. BM25 search
8. Hybrid search combining BM25 + vectors
9. Finding news for markets
10. Finding markets for news
11. Data cleanup (delete old news)
12. Statistics generation
13. Collection management

**Why This Violates SRP**:
- Changes to ChromaDB API → affects this class
- Changes to BM25 algorithm → affects this class
- Changes to search strategy → affects this class
- Changes to indexing logic → affects this class
- Changes to hybrid scoring → affects this class

**Recommended Refactoring**:
```
VectorStore (current)
    ↓
├── ChromaDBClient (database operations only)
├── BM25Index (keyword search only)
├── NewsIndexer (index news articles)
├── MarketIndexer (index markets)
├── HybridSearchEngine (combine BM25 + vector results)
└── SearchRepository (high-level search interface)
```

**Estimated Effort**: High (2-3 days)

---

### 2. ❌ `LLMClient` (src/utils/llm.py)

**Current Responsibilities**:
1. OpenAI API communication
2. Retry logic for failed requests
3. Building market forecasting prompts
4. Parsing prediction responses
5. Building news relevance prompts
6. Parsing relevance responses
7. Domain-specific prediction logic
8. Domain-specific analysis logic

**Why This Violates SRP**:
- Changes to OpenAI API → affects this class
- Changes to prompt structure → affects this class
- Changes to parsing logic → affects this class
- Changes to domain logic → affects this class

**Recommended Refactoring**:
```
LLMClient (current)
    ↓
├── LLMApiClient (API calls + retry logic only)
├── PromptBuilder (construct prompts)
├── ResponseParser (parse LLM responses)
└── LLMService (high-level operations using above)
```

**Example**:
```python
# BEFORE (SRP violation)
class LLMClient:
    async def predict_market_outcome(self, question, odds, news, date):
        prompt = self._build_forecasting_prompt(...)  # Prompt building
        response = await self.chat_completion(...)     # API call
        return self._parse_prediction_response(...)    # Parsing

    def _build_forecasting_prompt(...):  # Domain logic
    def _parse_prediction_response(...): # Parsing logic

# AFTER (SRP compliant)
class LLMApiClient:
    async def chat_completion(self, messages):
        """Only handles API communication"""

class ForecastingPromptBuilder:
    def build_prompt(self, question, odds, news, date):
        """Only builds prompts"""

class PredictionParser:
    def parse(self, response):
        """Only parses responses"""

class ForecastingService:
    def __init__(self, api_client, prompt_builder, parser):
        """Composes the above"""
```

**Estimated Effort**: Medium (1-2 days)

---

### 3. ❌ `TradingAgent` (src/agents/trader.py)

**Current Responsibilities**:
1. Trade execution (paper mode)
2. Trade execution (live mode)
3. Portfolio state management
4. Position tracking
5. P&L calculations
6. Position updates
7. Applying exit rules (stop loss, take profit)
8. Closing positions
9. Portfolio summary generation

**Why This Violates SRP**:
- Changes to trade execution → affects this class
- Changes to portfolio calculations → affects this class
- Changes to exit rules → affects this class
- Changes to P&L tracking → affects this class

**Recommended Refactoring**:
```
TradingAgent (current)
    ↓
├── TradeExecutor (execute trades only)
│   ├── PaperTradeExecutor
│   └── LiveTradeExecutor
├── PortfolioManager (manage portfolio state)
├── PositionTracker (track open positions)
├── ExitRuleEngine (apply exit rules)
└── PnLCalculator (calculate profit/loss)
```

**Estimated Effort**: High (2-3 days)

---

### 4. ❌ `AutonomousOrchestrator` (src/orchestrator.py)

**Current Responsibilities**:
1. Agent initialization
2. Trading cycle orchestration
3. Error handling and collection
4. Result building and formatting
5. Logging cycle progress
6. Circuit breaker checking
7. Continuous trading loop management
8. Manual trade execution
9. Status reporting

**Why This Violates SRP**:
- Changes to agent lifecycle → affects this class
- Changes to workflow → affects this class
- Changes to error handling → affects this class
- Changes to reporting → affects this class

**Recommended Refactoring**:
```
AutonomousOrchestrator (current)
    ↓
├── AgentFactory (create and initialize agents)
├── TradingWorkflow (orchestrate single cycle)
├── CycleResultBuilder (build result objects)
├── TradingScheduler (manage continuous trading)
└── StatusReporter (generate status reports)
```

**Estimated Effort**: High (2-3 days)

---

## Medium Violations (Medium Priority)

### 5. ⚠️ `NewsScraperAgent` (src/agents/news_scraper.py)

**Current Responsibilities**:
1. Multi-source news aggregation
2. Keyword extraction from config
3. Article filtering (quality, recency)
4. Vector store indexing
5. Continuous monitoring
6. Category-specific scraping

**Why This Violates SRP**:
- Changes to news sources → affects this class
- Changes to filtering logic → affects this class
- Changes to indexing → affects this class

**Recommended Refactoring**:
```
NewsScraperAgent (current)
    ↓
├── NewsSourceAggregator (fetch from sources)
├── NewsFilter (filter by quality/recency)
├── NewsIndexer (index in vector store)
└── NewsScraperService (compose above)
```

**Estimated Effort**: Medium (1-2 days)

---

### 6. ⚠️ `RiskManagerAgent` (src/agents/risk_manager.py)

**Current Responsibilities**:
1. Trade validation (multiple checks)
2. Position sizing calculations
3. Kelly Criterion implementation
4. Circuit breaker management
5. Risk score calculation
6. Confidence multipliers
7. Category exposure tracking

**Why This Violates SRP**:
- Changes to validation rules → affects this class
- Changes to position sizing → affects this class
- Changes to circuit breakers → affects this class

**Recommended Refactoring**:
```
RiskManagerAgent (current)
    ↓
├── TradeValidator (validate trades)
├── PositionSizer (calculate position sizes)
│   └── KellyCriterionCalculator
├── CircuitBreaker (manage circuit breakers)
└── RiskScoreCalculator (calculate risk scores)
```

**Estimated Effort**: Medium (1-2 days)

---

## Minor Violations (Low Priority)

### 7. 🟡 `ConfigManager` (src/utils/config.py)

**Current Responsibilities**:
1. Environment variable loading (Pydantic Settings)
2. YAML file loading
3. Configuration access methods
4. Market filter extraction
5. Risk limit extraction

**Why Minor**: Configuration management naturally bundles related concerns, but could be improved.

**Recommended Refactoring**:
```
ConfigManager (current)
    ↓
├── EnvConfigLoader (load from .env)
├── YamlConfigLoader (load from YAML)
└── ConfigFacade (provide unified access)
```

**Estimated Effort**: Low (< 1 day)

---

### 8. 🟡 `MarketIntelligenceAgent` (src/agents/market_intel.py)

**Current Responsibilities**:
1. Fetching markets from Gamma API
2. Market filtering
3. Market searching
4. Finding opportunities
5. Vector store indexing
6. Market summary generation

**Why Minor**: Agent coordination is its primary purpose, but indexing could be separated.

**Recommended**: Extract indexing to separate class.

**Estimated Effort**: Low (< 1 day)

---

## Models (Generally Good)

### ✅ Pydantic Models (src/models/)

**Good SRP Compliance**:
- `Market` - Only represents market data
- `NewsArticle` - Only represents news data
- `Prediction` - Only represents prediction data
- `Trade` - Only represents trade data
- `Portfolio` - Only represents portfolio data

**Minor Violations**:
- Some models have computed properties (e.g., `update_pnl()` in Trade)
- Could argue business logic should be in separate services

**Recommendation**: Move complex calculations to service classes if they become more complex.

---

## Summary Table

| Class | Lines | Responsibilities | Priority | Effort |
|-------|-------|-----------------|----------|--------|
| VectorStore | 651 | 13+ | 🔴 Critical | High |
| LLMClient | ~200 | 8+ | 🔴 Critical | Medium |
| TradingAgent | ~250 | 9+ | 🔴 Critical | High |
| AutonomousOrchestrator | ~250 | 9+ | 🔴 Critical | High |
| NewsScraperAgent | ~150 | 6 | ⚠️ Medium | Medium |
| RiskManagerAgent | ~250 | 7 | ⚠️ Medium | Medium |
| ConfigManager | ~100 | 5 | 🟡 Minor | Low |
| MarketIntelligenceAgent | ~200 | 6 | 🟡 Minor | Low |

---

## Refactoring Strategy

### Phase 1: Critical Violations (4-6 weeks)
1. **Week 1-2**: Refactor `VectorStore`
   - Extract ChromaDBClient
   - Extract HybridSearchEngine
   - Create SearchRepository facade

2. **Week 2-3**: Refactor `LLMClient`
   - Extract PromptBuilder
   - Extract ResponseParser
   - Create LLMService

3. **Week 3-4**: Refactor `TradingAgent`
   - Extract PortfolioManager
   - Extract ExitRuleEngine
   - Split PaperTradeExecutor / LiveTradeExecutor

4. **Week 5-6**: Refactor `AutonomousOrchestrator`
   - Extract TradingWorkflow
   - Extract AgentFactory
   - Extract StatusReporter

### Phase 2: Medium Violations (2-3 weeks)
5. Refactor `NewsScraperAgent`
6. Refactor `RiskManagerAgent`

### Phase 3: Minor Violations (1 week)
7. Clean up remaining minor violations

---

## Benefits of Refactoring

### Immediate Benefits:
✅ **Easier Testing**: Each class has fewer dependencies
✅ **Better Maintainability**: Changes isolated to single classes
✅ **Clearer Code**: Each class has obvious purpose
✅ **Easier Debugging**: Smaller classes, easier to trace issues

### Long-term Benefits:
✅ **Scalability**: Can swap implementations easily
✅ **Flexibility**: Easier to add new features
✅ **Team Collaboration**: Developers can work on different classes
✅ **Code Reuse**: Smaller classes more reusable

---

## Anti-Patterns to Avoid During Refactoring

### 1. God Objects
❌ Don't create new god objects while refactoring
✅ Keep new classes focused

### 2. Over-Engineering
❌ Don't create 50 tiny classes for simple logic
✅ Balance SRP with pragmatism

### 3. Breaking Changes
❌ Don't break existing tests/interfaces
✅ Use Facade pattern to maintain compatibility

### 4. Premature Optimization
❌ Don't optimize performance during refactoring
✅ Focus on structure first, optimize later

---

## Refactoring Principles to Follow

### 1. Boy Scout Rule
"Leave the code better than you found it"
- Small, incremental improvements
- Don't need to refactor everything at once

### 2. Red-Green-Refactor
- Keep tests passing (green)
- Refactor in small steps
- Run tests after each change

### 3. Strangler Fig Pattern
- Create new classes alongside old ones
- Gradually migrate callers
- Remove old code when safe

### 4. Facade Pattern
- Maintain backward compatibility
- Old interface delegates to new classes
- Allows gradual migration

---

## Example Refactoring: VectorStore → SearchRepository

### Before (SRP Violation):
```python
class VectorStore:
    def add_news_articles(self, articles): ...
    def add_markets(self, markets): ...
    def search_similar_markets(self, query): ...
    def search_relevant_news(self, query): ...
    def hybrid_search_markets(self, query): ...
    def hybrid_search_news(self, query): ...
    def find_news_for_market(self, market): ...
    def find_markets_for_news(self, article): ...
    def delete_old_news(self, days): ...
    def get_stats(self): ...
```

### After (SRP Compliant):
```python
# Single responsibility: Manage ChromaDB connection
class ChromaDBClient:
    def add(self, collection, documents, metadata): ...
    def query(self, collection, query_text, filters): ...

# Single responsibility: Keyword-based search
class BM25Index:
    def index_documents(self, documents): ...
    def search(self, query): ...

# Single responsibility: Combine search results
class HybridSearchEngine:
    def __init__(self, vector_client, bm25_index):
        self.vector_client = vector_client
        self.bm25_index = bm25_index

    def search(self, query, bm25_weight=0.3, vector_weight=0.7):
        bm25_results = self.bm25_index.search(query)
        vector_results = self.vector_client.query(query)
        return self._combine_results(bm25_results, vector_results)

# Facade for backward compatibility
class SearchRepository:
    def __init__(self):
        self.chroma = ChromaDBClient()
        self.bm25 = BM25Index()
        self.hybrid = HybridSearchEngine(self.chroma, self.bm25)

    def find_news_for_market(self, market):
        """High-level search operation"""
        return self.hybrid.search(market.question)
```

---

## Conclusion

The codebase has several **significant SRP violations**, particularly in:
1. `VectorStore` (651 lines, 13+ responsibilities)
2. `LLMClient` (8+ responsibilities)
3. `TradingAgent` (9+ responsibilities)
4. `AutonomousOrchestrator` (9+ responsibilities)

**Recommendation**:
- Start with `VectorStore` (biggest violation)
- Use Strangler Fig pattern for gradual migration
- Maintain backward compatibility with Facade pattern
- Refactor in phases over 8-10 weeks

**Priority**: While these are violations, the code is **functional and well-tested**. Refactoring should be done **incrementally** as the system matures, not as a big-bang rewrite.
