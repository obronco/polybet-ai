# Polybet AI - Autonomous Prediction Market Trading Agent

An intelligent, multi-agent system for autonomous trading on Polymarket prediction markets. Uses AI-powered news analysis, market forecasting, and risk management to identify and execute profitable trades.

## Features

### 🤖 Multi-Agent Architecture
- **News Scraper Agent**: Aggregates real-time news from multiple sources (NewsAPI, Tavily, RSS)
- **Market Intelligence Agent**: Retrieves and filters Polymarket markets
- **Analyst Agent**: Correlates news events with relevant markets using RAG
- **Forecasting Agent**: Generates probability predictions using LLM as "superforecaster"
- **Risk Manager Agent**: Validates trades and enforces comprehensive risk limits
- **Trading Agent**: Executes trades with paper trading and live trading support

### 🧠 AI-Powered Decision Making
- LLM-based market outcome predictions with confidence scoring
- **Hybrid Search**: BM25 + Vector embeddings for optimal retrieval
- Semantic search using ChromaDB vector store for news-market correlation
- RAG (Retrieval-Augmented Generation) for context-aware forecasting
- Bayesian reasoning and base rate analysis

### 📊 Risk Management
- Kelly Criterion position sizing
- Circuit breakers for drawdown protection
- Portfolio limits and exposure tracking
- Stop-loss and take-profit automation
- Comprehensive trade validation

### 📰 News Intelligence
- Multi-source news aggregation (NewsAPI, Tavily, RSS)
- Automatic news relevance scoring
- Semantic search for market-news matching
- Real-time monitoring and breaking news detection

### 💹 Trading Features
- Paper trading mode for testing strategies
- Live trading on Polymarket DEX
- Automated trade execution
- Position tracking and P&L monitoring
- Portfolio analytics and reporting

## Installation

### Prerequisites
- Python 3.9+
- API Keys:
  - OpenAI API key (required)
  - NewsAPI key (required)
  - Tavily API key (optional but recommended)
  - Polymarket API credentials (for live trading)
- Polygon wallet with USDC (for live trading)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd polybet-ai
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

5. Edit configuration files:
- `config/markets_config.yaml` - Market selection criteria
- `config/risk_config.yaml` - Risk management rules

## Configuration

### Environment Variables (.env)

Required:
```
OPENAI_API_KEY=your_openai_key
NEWSAPI_KEY=your_newsapi_key
POLYGON_WALLET_PRIVATE_KEY=your_private_key
POLYGON_WALLET_ADDRESS=your_wallet_address
```

Optional:
```
TAVILY_API_KEY=your_tavily_key
PAPER_TRADING_MODE=true
MAX_BET_SIZE_PCT=0.03
MIN_EDGE_REQUIRED=0.05
```

### Market Configuration (config/markets_config.yaml)

```yaml
market_filters:
  categories:
    - Politics
    - Crypto
    - Sports
  min_liquidity_usd: 10000
  max_spread: 0.05
  min_time_to_resolution_hours: 24
```

### Risk Configuration (config/risk_config.yaml)

```yaml
risk_limits:
  max_bet_size_pct: 0.03  # 3% of bankroll per trade
  max_daily_loss_pct: 0.10  # Stop at 10% daily loss
  min_edge: 0.05  # Minimum 5% edge required
  min_confidence: 6  # Minimum confidence (1-10)

position_sizing:
  method: kelly_criterion
  kelly_fraction: 0.5  # Half Kelly for optimal growth with reduced variance
```

## Usage

### Command-Line Interface

Run autonomous trading:
```bash
python scripts/cli.py run
```

Run with custom interval:
```bash
python scripts/cli.py run --interval 30  # 30-minute cycles
```

Run a single cycle (test mode):
```bash
python scripts/cli.py cycle
```

List active markets:
```bash
python scripts/cli.py markets
python scripts/cli.py markets --category Politics --limit 10
```

Search news:
```bash
python scripts/cli.py news --keywords "election,president" --hours 24
```

Analyze and trade a specific market:
```bash
python scripts/cli.py trade <market_id>
python scripts/cli.py trade <market_id> --force  # Override risk checks
```

Check agent status:
```bash
python scripts/cli.py status
```

Verify configuration:
```bash
python scripts/cli.py config-check
```

### Live Trading vs Paper Trading

**Paper Trading (Default):**
```bash
python scripts/cli.py --paper-trading run
```

**Live Trading (Real Money):**
```bash
python scripts/cli.py --live-trading run
```

⚠️ **Warning**: Live trading uses real funds. Thoroughly test with paper trading first!

## How It Works

### Autonomous Trading Cycle

1. **News Scraping**: Fetch latest news from configured sources
2. **Market Retrieval**: Get active Polymarket markets matching filters
3. **Correlation Analysis**: Use RAG to find news-market correlations
4. **Opportunity Ranking**: Score opportunities by relevance, liquidity, and edge
5. **Prediction**: Generate AI forecasts for top opportunities
6. **Risk Assessment**: Validate each trade against risk criteria
7. **Trade Execution**: Execute approved trades
8. **Position Management**: Update P&L and apply exit rules

### Multi-Agent Workflow

```
┌─────────────┐
│ News Scraper│──────┐
└─────────────┘      │
                     ├──> ┌──────────┐      ┌────────────┐
┌──────────────┐     │    │ Analyst  │─────>│ Forecaster │
│Market Intel  │─────┘    │  Agent   │      │   Agent    │
└──────────────┘          └──────────┘      └────────────┘
                                                    │
                                                    ▼
                          ┌──────────┐      ┌─────────────┐
                          │  Trader  │<─────│Risk Manager │
                          │  Agent   │      │    Agent    │
                          └──────────┘      └─────────────┘
```

## Project Structure

```
polybet-ai/
├── src/
│   ├── agents/              # Agent implementations
│   │   ├── news_scraper.py
│   │   ├── market_intel.py
│   │   ├── analyst.py
│   │   ├── forecaster.py
│   │   ├── risk_manager.py
│   │   └── trader.py
│   ├── api/                 # API clients
│   │   ├── gamma.py
│   │   ├── polymarket.py
│   │   └── news_sources.py
│   ├── models/              # Data models
│   │   ├── market.py
│   │   ├── news.py
│   │   └── trade.py
│   ├── rag/                 # Vector store
│   │   └── vector_store.py
│   ├── utils/               # Utilities
│   │   ├── config.py
│   │   ├── logger.py
│   │   ├── llm.py
│   │   └── prompts.py
│   └── orchestrator.py      # Main coordinator
├── scripts/
│   └── cli.py               # Command-line interface
├── config/
│   ├── markets_config.yaml
│   └── risk_config.yaml
├── tests/                   # Test suite
├── requirements.txt
├── .env.example
└── README.md
```

## Advanced Features

### Hybrid Search: BM25 + Vector Embeddings

The system uses **hybrid retrieval** combining two complementary search methods:

**BM25 (Best Matching 25)**
- Probabilistic keyword-based ranking function
- Excels at exact keyword matches and specific terms
- Fast and efficient for precision retrieval
- Parameters: k1=1.5 (term frequency saturation), b=0.75 (length normalization)

**Vector Embeddings (OpenAI)**
- Dense semantic representations using `text-embedding-3-small`
- Captures meaning and context beyond keywords
- Finds semantically similar content even with different wording
- Stored in ChromaDB with cosine similarity

**Hybrid Combination**
```python
hybrid_score = (bm25_score * 0.3) + (vector_score * 0.7)
```

**Why Hybrid?**
- **BM25** catches specific terminology (e.g., "BTC" vs "Bitcoin")
- **Vectors** understand synonyms and context (e.g., "price surge" = "value increases")
- **Together** they provide robust, high-quality retrieval

**Tunable Weights:**
- News → Markets: 40% BM25, 60% Vector (higher keyword weight for news matching)
- Markets → News: 30% BM25, 70% Vector (standard balance)
- Configurable per query for optimization

**Performance Benefits:**
- Better precision and recall than either method alone
- Reduces false positives from pure semantic search
- Captures both exact and fuzzy matches

## Safety Features

### Circuit Breakers
- Daily loss limit (default: 15%)
- Consecutive loss limit
- Rapid drawdown protection

### Position Limits
- Maximum bet size (default: 3% of bankroll)
- Maximum concurrent positions (default: 10)
- Category exposure limits (default: 20% per category)

### Trade Validation
- Minimum edge requirement (default: 5%)
- Minimum confidence threshold (default: 6/10)
- Liquidity checks
- Slippage protection

## Development

### Running Tests
```bash
pytest tests/
pytest tests/ --cov=src  # With coverage
```

### Code Quality
```bash
black src/  # Format code
flake8 src/  # Lint
mypy src/  # Type checking
```

## Performance Tracking

The system tracks:
- Total P&L
- ROI (Return on Investment)
- Win rate
- Sharpe ratio
- Average trade duration
- Model calibration (predicted vs actual outcomes)

View performance:
```bash
python scripts/cli.py status
```

## Troubleshooting

### Common Issues

**"No news articles found"**
- Check API keys in `.env`
- Verify network connectivity
- Review `markets_config.yaml` keywords

**"No active markets found"**
- Adjust market filters in `markets_config.yaml`
- Check Polymarket API status
- Verify category filters

**"Circuit breaker triggered"**
- Daily loss limit exceeded
- Edit `risk_config.yaml` to adjust thresholds
- Reset manually after reviewing performance

**Import errors**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`
- Check Python version (3.9+ required)

## Legal & Compliance

### Important Notices

1. **Geographic Restrictions**: Polymarket restricts US persons and certain jurisdictions from trading. Verify eligibility before use.

2. **Financial Risk**: Prediction markets involve financial risk. Only trade with funds you can afford to lose.

3. **No Guarantees**: This system provides no guarantee of profits. Past performance does not indicate future results.

4. **API Terms**: Respect all API provider terms of service (OpenAI, NewsAPI, Tavily, Polymarket).

5. **Responsible Usage**: Implement appropriate position sizing and risk management. Start with paper trading.

## Roadmap

- [ ] Web dashboard (Streamlit/Gradio)
- [ ] Telegram/Discord notifications
- [ ] Advanced backtesting engine
- [ ] Multi-market arbitrage detection
- [ ] Machine learning model calibration
- [ ] Portfolio optimization
- [ ] Additional news sources (Twitter/X API)
- [ ] Market sentiment analysis
- [ ] Historical performance analytics

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Resources

- [Polymarket Docs](https://docs.polymarket.com)
- [Polymarket Agents Framework](https://github.com/Polymarket/agents)
- [OpenAI API Reference](https://platform.openai.com/docs)
- [NewsAPI Documentation](https://newsapi.org/docs)

## License

MIT License - See LICENSE file for details.

## Disclaimer

This software is for educational and research purposes. The authors are not responsible for any financial losses incurred through use of this system. Always conduct your own research and consult with qualified financial advisors before trading.

---

**Built with**: Python, OpenAI, LangChain, ChromaDB, Polymarket API, NewsAPI, Tavily

**Author**: Polybet AI Team
