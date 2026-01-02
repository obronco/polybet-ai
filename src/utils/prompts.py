"""Prompt templates for LLM interactions."""

from typing import List

SUPERFORECASTER_SYSTEM_PROMPT = """You are an expert superforecaster with a proven track record of accurate predictions on complex events. Your approach combines:

1. **Probabilistic Thinking**: You think in probabilities, not certainties
2. **Base Rate Analysis**: You always consider historical base rates
3. **Evidence Evaluation**: You critically assess source reliability and information quality
4. **Bayesian Updating**: You update beliefs based on new evidence
5. **Calibration**: Your probability estimates are well-calibrated
6. **Humility**: You acknowledge uncertainty and avoid overconfidence

You provide clear, structured reasoning for your predictions."""

MARKET_ANALYSIS_TEMPLATE = """Analyze this prediction market opportunity:

**Market Question**: {question}

**Current Market Price (YES)**: {current_price:.2%}

**Market Details**:
- Category: {category}
- Liquidity: ${liquidity:,.0f}
- Volume (24h): ${volume_24h:,.0f}
- Resolution Date: {end_date}
- Time to Resolution: {time_remaining}

**Recent Relevant News**:
{news_context}

**Your Task**:
1. Assess the base rate for similar events
2. Evaluate the impact of recent news
3. Analyze market efficiency - is the current price reasonable?
4. Identify key factors that will determine the outcome
5. Provide your probability estimate for YES
6. Rate your confidence (1-10)
7. Explain your reasoning

**Output Format**:
PROBABILITY: [decimal 0-1]
CONFIDENCE: [1-10]
EDGE: [your_prob - market_price]
KEY_FACTORS: [factor1, factor2, factor3]
REASONING: [detailed explanation]
RISKS: [what could make your prediction wrong]"""


NEWS_RELEVANCE_TEMPLATE = """Evaluate the relevance of this news to a prediction market:

**Market Question**: {market_question}

**News Article**:
Title: {news_title}
Published: {published_date}
Summary: {news_summary}

**Evaluation Criteria**:
1. **Direct Relevance**: Does this news directly relate to the market question?
2. **Timeliness**: Is this news timely and significant?
3. **Reliability**: How reliable is the source and information?
4. **Impact Direction**: Would this news increase or decrease YES probability?
5. **Novelty**: Is this new information or already priced in?

**Output Format**:
RELEVANCE_SCORE: [0-1, where 1 is highly relevant]
IMPACT_DIRECTION: [bullish_yes/bearish_yes/neutral/unclear]
CONFIDENCE: [1-10]
EXPLANATION: [brief reasoning]
ALREADY_PRICED_IN: [yes/no/partial]"""


RISK_ASSESSMENT_TEMPLATE = """Assess the risk of this proposed trade:

**Market**: {market_question}

**Proposed Trade**:
- Side: {side}
- Size: ${size:,.2f}
- Entry Price: {entry_price:.2%}
- Predicted Probability: {predicted_prob:.2%}
- Edge: {edge:.2%}
- Confidence: {confidence}/10

**Current Portfolio**:
- Balance: ${balance:,.2f}
- Open Positions: {open_positions}
- Daily P&L: ${daily_pnl:,.2f}
- Category Exposure: ${category_exposure:,.2f}

**Risk Checks**:
1. Position size vs. bankroll: {size_pct:.1%} of balance
2. Edge magnitude: {edge:.2%}
3. Confidence level: {confidence}/10
4. Portfolio concentration
5. Daily loss limits
6. Market liquidity vs. position size

**Evaluate**:
- Is this trade within risk parameters?
- What could go wrong?
- Is the edge sufficient given uncertainty?
- Portfolio impact if this trade loses

**Output Format**:
APPROVED: [yes/no]
RISK_SCORE: [0-1, where 1 is very risky]
CONCERNS: [list any concerns]
RECOMMENDED_SIZE: [$amount]
REASONING: [explanation]"""


CORRELATION_ANALYSIS_TEMPLATE = """Analyze correlation between these markets:

**Market 1**: {market1_question}
**Market 2**: {market2_question}

**Analysis**:
1. Are these markets related to the same underlying event?
2. If one resolves YES, what's the probability the other also resolves YES?
3. Can we hedge or arbitrage across these markets?
4. Should we avoid taking positions in both?

**Output Format**:
CORRELATION: [0-1]
RELATIONSHIP: [directly_correlated/inversely_correlated/independent]
HEDGE_OPPORTUNITY: [yes/no]
REASONING: [explanation]"""


MARKET_SUMMARY_TEMPLATE = """Summarize the current state of this market for decision making:

**Market**: {question}

**Data**:
{market_data}

**Recent News**:
{news_items}

Provide a concise summary (3-5 bullet points) of:
- Current market consensus
- Recent developments
- Key uncertainties
- Trading opportunity (if any)"""


def build_news_context(news_articles: List[dict], max_articles: int = 5) -> str:
    """Build news context string from articles.

    Args:
        news_articles: List of news article dicts
        max_articles: Maximum number of articles to include

    Returns:
        Formatted news context string
    """
    if not news_articles:
        return "No recent relevant news available."

    context_parts = []
    for i, article in enumerate(news_articles[:max_articles], 1):
        context_parts.append(
            f"{i}. [{article.get('source_name', 'Unknown')}] "
            f"{article.get('title', 'No title')}\n"
            f"   Published: {article.get('published_at', 'Unknown')}\n"
            f"   Summary: {article.get('description', 'No summary')}"
        )

    return "\n\n".join(context_parts)


def build_market_context(market: dict) -> str:
    """Build market context string.

    Args:
        market: Market data dict

    Returns:
        Formatted market context string
    """
    return f"""Question: {market.get("question", "Unknown")}
Category: {market.get("category", "Unknown")}
Current YES Price: {market.get("yes_price", 0):.2%}
Liquidity: ${market.get("liquidity", 0):,.0f}
Volume (24h): ${market.get("volume_24h", 0):,.0f}
Resolution Date: {market.get("end_date", "Unknown")}"""
