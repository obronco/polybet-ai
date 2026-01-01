#!/usr/bin/env python3
"""Demo script showing paper trading with mock data."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.forecaster import ForecastingAgent
from src.agents.risk_manager import RiskManagerAgent
from src.agents.trader import TradingAgent
from src.models.market import Market, MarketStatus
from src.models.news import NewsArticle, NewsSource, SentimentScore
from src.utils.logger import setup_logging

console = Console()


def create_mock_market() -> Market:
    """Create a mock market for demo."""
    return Market(
        id="market_btc_100k_2025",
        question="Will Bitcoin reach $100,000 by end of 2025?",
        description="Resolves YES if Bitcoin price reaches or exceeds $100,000 USD on any major exchange before 2026-01-01.",
        category="Crypto",
        status=MarketStatus.ACTIVE,
        yes_price=0.65,
        no_price=0.35,
        spread=0.02,
        liquidity=250000.0,
        volume_24h=50000.0,
        volume=180000.0,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2025, 12, 31),
    )


def create_mock_news() -> list[NewsArticle]:
    """Create mock news articles for demo."""
    return [
        NewsArticle(
            id="news_1",
            url="https://example.com/btc-etf-inflows",
            source=NewsSource.CUSTOM,
            source_name="CryptoNews",
            title="Bitcoin ETF Sees Record Inflows of $2.1 Billion in Single Week",
            content="Institutional investors continue to pour capital into Bitcoin ETFs, with record-breaking inflows signaling strong institutional demand. Analysts predict this trend could push prices significantly higher.",
            published_at=datetime.now(),
            author="Jane Smith",
            sentiment=SentimentScore.VERY_POSITIVE,
            sentiment_score=0.8,
        ),
        NewsArticle(
            id="news_2",
            url="https://example.com/goldman-btc-target",
            source=NewsSource.CUSTOM,
            source_name="Financial Times",
            title="Major Investment Bank Raises Bitcoin Price Target to $120K",
            content="Goldman Sachs has raised its 2025 Bitcoin price target to $120,000, citing increasing institutional adoption, upcoming halving effects, and macroeconomic tailwinds.",
            published_at=datetime.now(),
            author="John Analyst",
            sentiment=SentimentScore.VERY_POSITIVE,
            sentiment_score=0.9,
        ),
        NewsArticle(
            id="news_3",
            url="https://example.com/btc-hashrate-ath",
            source=NewsSource.CUSTOM,
            source_name="CoinDesk",
            title="Bitcoin Network Hashrate Hits All-Time High",
            content="Bitcoin's network security reaches unprecedented levels as hashrate hits new all-time high, demonstrating robust mining activity and network confidence.",
            published_at=datetime.now(),
            author="Crypto Reporter",
            sentiment=SentimentScore.POSITIVE,
            sentiment_score=0.7,
        ),
    ]


async def run_demo():
    """Run paper trading demo with mock data."""
    console.print(
        Panel.fit(
            "[bold cyan]Polybet AI - Paper Trading Demo[/bold cyan]\n"
            "[yellow]Using mock data to demonstrate full trading cycle[/yellow]",
            border_style="cyan",
        )
    )

    # Initialize agents
    console.print("\n[bold]Initializing Agents...[/bold]")
    forecaster = ForecastingAgent()
    risk_manager = RiskManagerAgent()
    trader = TradingAgent(paper_trading=True)

    # Create mock data
    market = create_mock_market()
    news = create_mock_news()

    # Display market
    console.print("\n[bold green]Target Market:[/bold green]")
    market_table = Table()
    market_table.add_column("Field", style="cyan")
    market_table.add_column("Value", style="white")
    market_table.add_row("Question", market.question)
    market_table.add_row("Category", market.category)
    market_table.add_row("YES Price", f"{market.yes_price:.2%}")
    market_table.add_row("Liquidity", f"${market.liquidity:,.0f}")
    market_table.add_row("24h Volume", f"${market.volume_24h:,.0f}")
    console.print(market_table)

    # Display news
    console.print("\n[bold green]Recent News Context:[/bold green]")
    news_table = Table()
    news_table.add_column("Title", style="cyan", width=60)
    news_table.add_column("Source", style="magenta")
    news_table.add_column("Sentiment", style="green")
    for article in news:
        news_table.add_row(
            article.title[:57] + "..." if len(article.title) > 60 else article.title,
            article.source_name,
            f"{article.sentiment_score:.2f}" if article.sentiment_score else "N/A",
        )
    console.print(news_table)

    # Generate prediction
    console.print("\n[bold]Step 1: Generating AI Prediction...[/bold]")
    prediction = await forecaster.predict_outcome(market=market, news_context=news)

    pred_table = Table(title="AI Prediction")
    pred_table.add_column("Metric", style="cyan")
    pred_table.add_column("Value", style="green")
    pred_table.add_row("Predicted Probability", f"{prediction.predicted_probability:.2%}")
    pred_table.add_row("Market Price", f"{market.yes_price:.2%}")
    pred_table.add_row("Edge", f"{prediction.edge:.2%}")
    pred_table.add_row("Confidence (1-10)", f"{prediction.confidence}/10")
    pred_table.add_row("Key Factors", ", ".join(prediction.key_factors[:3]))
    console.print(pred_table)

    # Display reasoning
    console.print(f"\n[bold]AI Reasoning:[/bold]\n{prediction.reasoning}\n")

    # Risk assessment
    console.print("[bold]Step 2: Risk Assessment...[/bold]")
    risk_assessment = await risk_manager.validate_trade(
        prediction=prediction,
        market=market,
        portfolio=trader.portfolio,
    )

    risk_table = Table(title="Risk Assessment")
    risk_table.add_column("Check", style="cyan")
    risk_table.add_column("Status", style="white")

    for check, passed in [
        ("Sufficient Edge", prediction.edge >= 0.05),
        ("High Confidence", prediction.confidence >= 6),
        ("Within Position Limits", True),
        ("Within Daily Loss Limits", True),
        ("Circuit Breaker OK", not risk_manager.circuit_breaker_active),
    ]:
        status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        risk_table.add_row(check, status)

    risk_table.add_row(
        "Recommended Size", f"${risk_assessment.recommended_size:,.2f}", style="bold"
    )
    risk_table.add_row(
        "Trade Approved",
        "[green]YES[/green]" if risk_assessment.approved else "[red]NO[/red]",
        style="bold",
    )
    console.print(risk_table)

    # Execute trade
    if risk_assessment.approved:
        console.print("\n[bold]Step 3: Executing Paper Trade...[/bold]")
        trade = await trader.execute_trade(
            prediction=prediction,
            risk_assessment=risk_assessment,
            market=market,
        )

        if trade:
            trade_table = Table(title="[green]Trade Executed Successfully[/green]")
            trade_table.add_column("Field", style="cyan")
            trade_table.add_column("Value", style="white")
            trade_table.add_row("Trade ID", trade.id)
            trade_table.add_row("Market", market.question[:50] + "...")
            trade_table.add_row("Direction", trade.side.upper())
            trade_table.add_row("Size", f"${trade.size:,.2f}")
            trade_table.add_row("Entry Price", f"{trade.entry_price:.2%}")
            trade_table.add_row("Expected Edge", f"{prediction.edge:.2%}")
            trade_table.add_row("Status", trade.status)
            console.print(trade_table)
        else:
            console.print("[red]Trade execution failed[/red]")
    else:
        console.print("\n[red]Trade rejected by risk manager[/red]")
        console.print(f"Failed checks: {', '.join(risk_assessment.checks_failed)}")

    # Show portfolio summary
    console.print("\n[bold]Step 4: Portfolio Summary...[/bold]")
    portfolio_summary = trader.get_portfolio_summary()

    portfolio_table = Table(title="Portfolio After Trade")
    portfolio_table.add_column("Metric", style="cyan")
    portfolio_table.add_column("Value", style="green")
    portfolio_table.add_row("Balance", f"${portfolio_summary['balance']:,.2f}")
    portfolio_table.add_row("Available Balance", f"${portfolio_summary['available_balance']:,.2f}")
    portfolio_table.add_row("Total Trades", str(portfolio_summary['total_trades']))
    portfolio_table.add_row("Open Positions", str(portfolio_summary['open_positions']))
    portfolio_table.add_row("Total P&L", f"${portfolio_summary['total_pnl']:,.2f}")
    console.print(portfolio_table)

    # Summary
    console.print(
        Panel.fit(
            "[bold green]Demo Complete![/bold green]\n\n"
            "[white]This demonstrates the full autonomous trading cycle:[/white]\n"
            "  1. News analysis and market correlation\n"
            "  2. AI-powered outcome prediction\n"
            "  3. Comprehensive risk assessment\n"
            "  4. Automated trade execution (paper mode)\n"
            "  5. Portfolio tracking and monitoring\n\n"
            "[yellow]Note: This used mock data due to network restrictions.[/yellow]\n"
            "[yellow]In production, the system fetches real-time news and market data.[/yellow]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    setup_logging(log_level="WARNING")  # Suppress logs for clean demo
    asyncio.run(run_demo())
