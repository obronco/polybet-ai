#!/usr/bin/env python3
"""Command-line interface for Polybet AI."""

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator import AutonomousOrchestrator
from src.utils.config import config
from src.utils.logger import setup_logging

console = Console()


@click.group()
@click.option("--log-level", default="INFO", help="Logging level")
@click.option("--paper-trading/--live-trading", default=True, help="Trading mode")
@click.pass_context
def cli(ctx, log_level, paper_trading):
    """Polybet AI - Autonomous prediction market trading agent."""
    setup_logging(log_level=log_level)
    ctx.ensure_object(dict)
    ctx.obj["paper_trading"] = paper_trading
    console.print(f"[bold blue]Polybet AI[/bold blue] - {'Paper Trading' if paper_trading else 'Live Trading'} Mode")


@cli.command()
@click.option("--interval", default=None, type=int, help="Trading cycle interval (minutes)")
@click.pass_context
def run(ctx, interval):
    """Run autonomous trading agent continuously."""
    console.print("\n[bold green]Starting Autonomous Trading Agent[/bold green]\n")

    orchestrator = AutonomousOrchestrator(paper_trading=ctx.obj["paper_trading"])

    try:
        asyncio.run(orchestrator.run_continuous(interval_minutes=interval))
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
        orchestrator.stop()


@cli.command()
@click.pass_context
def cycle(ctx):
    """Run a single trading cycle."""
    console.print("\n[bold green]Running Single Trading Cycle[/bold green]\n")

    orchestrator = AutonomousOrchestrator(paper_trading=ctx.obj["paper_trading"])

    async def run_cycle():
        results = await orchestrator.run_trading_cycle()
        display_cycle_results(results)
        display_portfolio(orchestrator.trader.get_portfolio_summary())

    asyncio.run(run_cycle())


@cli.command()
@click.option("--category", default=None, help="Filter by category")
@click.option("--limit", default=20, help="Number of markets to show")
def markets(category, limit):
    """List active prediction markets."""
    console.print(f"\n[bold green]Fetching Markets[/bold green]\n")

    from src.agents.market_intel import MarketIntelligenceAgent

    async def fetch_markets():
        async with MarketIntelligenceAgent() as intel:
            if category:
                markets_list = await intel.get_markets_by_category(category, limit=limit)
            else:
                markets_list = await intel.get_active_markets(limit=limit)

            display_markets(markets_list)

    asyncio.run(fetch_markets())


@cli.command()
@click.option("--keywords", required=True, help="Search keywords (comma-separated)")
@click.option("--hours", default=24, help="Hours to look back")
def news(keywords, hours):
    """Search for news articles."""
    console.print(f"\n[bold green]Searching News[/bold green]\n")

    from src.agents.news_scraper import NewsScraperAgent

    keyword_list = [k.strip() for k in keywords.split(",")]

    async def fetch_news():
        scraper = NewsScraperAgent()
        articles = await scraper.scrape_targeted_news(keyword_list, lookback_hours=hours)
        display_news(articles)

    asyncio.run(fetch_news())


@cli.command()
@click.argument("market_id")
@click.option("--force", is_flag=True, help="Force trade even if risk checks fail")
@click.pass_context
def trade(ctx, market_id, force):
    """Analyze and potentially trade a specific market."""
    console.print(f"\n[bold green]Analyzing Market: {market_id}[/bold green]\n")

    orchestrator = AutonomousOrchestrator(paper_trading=ctx.obj["paper_trading"])

    async def execute_trade():
        result = await orchestrator.manual_trade(market_id, force=force)

        if result.get("success"):
            console.print("[bold green]✓ Trade Executed Successfully[/bold green]")
            console.print(f"Trade ID: {result.get('trade_id')}")
        else:
            console.print(f"[bold red]✗ Trade Rejected: {result.get('reason')}[/bold red]")

        if "prediction" in result:
            pred = result["prediction"]
            console.print(f"\nPredicted Probability: {pred['probability']:.2%}")
            console.print(f"Confidence: {pred['confidence']}/10")
            console.print(f"Edge: {pred['edge']:.2%}")

        if "checks_failed" in result:
            console.print("\nFailed Checks:")
            for check in result["checks_failed"]:
                console.print(f"  - {check}")

    asyncio.run(execute_trade())


@cli.command()
@click.pass_context
def status(ctx):
    """Show current agent status and portfolio."""
    orchestrator = AutonomousOrchestrator(paper_trading=ctx.obj["paper_trading"])

    async def show_status():
        status_data = await orchestrator.get_status()

        console.print("\n[bold blue]Agent Status[/bold blue]")
        console.print(f"Running: {status_data['running']}")
        console.print(f"Cycles Completed: {status_data['cycle_count']}")
        console.print(f"Paper Trading: {status_data['paper_trading']}")
        console.print(f"Circuit Breaker: {'🔴 ACTIVE' if status_data['circuit_breaker_active'] else '🟢 Inactive'}")

        console.print("\n[bold blue]Portfolio Summary[/bold blue]")
        display_portfolio(status_data['portfolio'])

    asyncio.run(show_status())


@cli.command()
def config_check():
    """Check configuration and API keys."""
    console.print("\n[bold blue]Configuration Check[/bold blue]\n")

    checks = {
        "OpenAI API Key": bool(config.settings.openai_api_key.get_secret_value()),
        "NewsAPI Key": bool(config.settings.newsapi_key.get_secret_value()),
        "Tavily API Key": bool(config.settings.tavily_api_key.get_secret_value()),
        "Wallet Private Key": bool(config.settings.polygon_wallet_private_key.get_secret_value()),
        "Paper Trading Mode": config.settings.paper_trading_mode,
    }

    for check_name, check_value in checks.items():
        icon = "✓" if check_value else "✗"
        color = "green" if check_value else "red"
        console.print(f"[{color}]{icon}[/{color}] {check_name}: {check_value}")


# Display helpers


def display_markets(markets):
    """Display markets in a table."""
    if not markets:
        console.print("[yellow]No markets found[/yellow]")
        return

    table = Table(title=f"Active Markets ({len(markets)})")
    table.add_column("Question", style="cyan", width=50)
    table.add_column("Category", style="magenta")
    table.add_column("YES Price", justify="right", style="green")
    table.add_column("Liquidity", justify="right", style="blue")
    table.add_column("Volume 24h", justify="right", style="yellow")

    for market in markets[:20]:  # Show first 20
        table.add_row(
            market.question[:47] + "..." if len(market.question) > 50 else market.question,
            market.category,
            f"{market.yes_price:.2%}",
            f"${market.liquidity:,.0f}",
            f"${market.volume_24h:,.0f}",
        )

    console.print(table)


def display_news(articles):
    """Display news articles in a table."""
    if not articles:
        console.print("[yellow]No news articles found[/yellow]")
        return

    table = Table(title=f"News Articles ({len(articles)})")
    table.add_column("Title", style="cyan", width=60)
    table.add_column("Source", style="magenta")
    table.add_column("Published", style="blue")

    for article in articles:
        table.add_row(
            article.title[:57] + "..." if len(article.title) > 60 else article.title,
            article.source_name,
            article.published_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


def display_portfolio(portfolio):
    """Display portfolio summary."""
    table = Table(title="Portfolio")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Balance", f"${portfolio['balance']:,.2f}")
    table.add_row("Total P&L", f"${portfolio['total_pnl']:,.2f}")
    table.add_row("ROI", f"{portfolio['roi']:.2f}%")
    table.add_row("Total Trades", str(portfolio['total_trades']))
    table.add_row("Open Positions", str(portfolio['open_positions']))
    table.add_row("Win Rate", f"{portfolio['win_rate']:.1f}%")
    table.add_row("Available Balance", f"${portfolio['available_balance']:,.2f}")

    console.print(table)


def display_cycle_results(results):
    """Display trading cycle results."""
    table = Table(title=f"Cycle #{results['cycle']} Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("News Articles Found", str(results['news_articles_found']))
    table.add_row("Markets Analyzed", str(results['markets_analyzed']))
    table.add_row("Opportunities Identified", str(results['opportunities_identified']))
    table.add_row("Predictions Made", str(results['predictions_made']))
    table.add_row("Trades Executed", str(results['trades_executed']))
    table.add_row("Trades Rejected", str(results['trades_rejected']))
    table.add_row("Duration", f"{results['duration_seconds']:.1f}s")

    console.print(table)


if __name__ == "__main__":
    cli(obj={})
