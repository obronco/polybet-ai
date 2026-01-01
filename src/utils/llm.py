"""LLM utilities for AI-powered predictions and analysis."""

from typing import Any, Dict, List, Optional

from aiolimiter import AsyncLimiter
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import config
from .logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Client for interacting with Large Language Models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """Initialize LLM client.

        Args:
            api_key: OpenAI API key (defaults to config)
            model: Model name (defaults to config)
            temperature: Sampling temperature
        """
        self.api_key = api_key or config.settings.openai_api_key.get_secret_value()
        self.model = model or config.settings.openai_model
        self.temperature = temperature
        self.client = AsyncOpenAI(api_key=self.api_key)

        # Rate limiter: max calls per minute from config
        rate_limit = config.settings.api_rate_limit_calls_per_minute
        self.rate_limiter = AsyncLimiter(max_rate=rate_limit, time_period=60)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """Get chat completion from LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments for API

        Returns:
            Generated text response
        """
        temp = temperature if temperature is not None else self.temperature

        logger.info(
            "llm_chat_completion",
            model=self.model,
            temperature=temp,
            num_messages=len(messages),
        )

        try:
            # Rate limit API calls to prevent quota exhaustion
            async with self.rate_limiter:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=max_tokens,
                    **kwargs,
                )

            content = response.choices[0].message.content
            logger.info(
                "llm_completion_success",
                tokens_used=response.usage.total_tokens,
            )
            return content

        except Exception as e:
            logger.error("llm_completion_error", error=str(e))
            raise

    async def predict_market_outcome(
        self,
        question: str,
        current_odds: float,
        news_context: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """Use LLM as superforecaster to predict market outcome.

        Args:
            question: Market question
            current_odds: Current market odds for YES
            news_context: Relevant news context
            end_date: Market resolution date

        Returns:
            Dict with prediction, confidence, and reasoning
        """
        prompt = self._build_forecasting_prompt(
            question, current_odds, news_context, end_date
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert superforecaster with a track record of accurate predictions. You analyze information carefully, consider base rates, update beliefs based on evidence, and provide well-calibrated probability estimates.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await self.chat_completion(messages, temperature=0.7)

        # Parse response (in production, use structured output)
        return self._parse_prediction_response(response)

    def _build_forecasting_prompt(
        self,
        question: str,
        current_odds: float,
        news_context: str,
        end_date: str,
    ) -> str:
        """Build prompt for market forecasting."""
        return f"""You are analyzing a prediction market to determine the probability of an outcome.

Market Question: {question}
Current Market Odds (YES): {current_odds:.2%}
Resolution Date: {end_date}

Recent Relevant News and Context:
{news_context}

Please analyze this market by following these steps:

1. **Base Rate Analysis**: What is the historical base rate for similar events?

2. **Key Factors**: Identify the key factors that will determine this outcome.

3. **News Impact**: How does the recent news affect the probability? Is it significant, reliable, and timely?

4. **Market Analysis**: Is the current market price ({current_odds:.2%}) reasonable? What might the market be missing or overweighting?

5. **Probability Estimate**: Provide your probability estimate for the YES outcome.

6. **Confidence Level**: Rate your confidence (1-10, where 10 is extremely confident).

7. **Reasoning**: Explain your reasoning concisely.

Format your response as:
PROBABILITY: [your estimate as decimal 0-1]
CONFIDENCE: [1-10]
REASONING: [your detailed reasoning]
KEY_FACTORS: [comma-separated list of key factors]

Think step-by-step and be precise in your analysis."""

    def _parse_prediction_response(self, response: str) -> Dict[str, Any]:
        """Parse structured prediction from LLM response.

        Args:
            response: Raw LLM response

        Returns:
            Parsed prediction dict

        Raises:
            ValueError: If parsing fails or values are invalid
        """
        result = {
            "probability": None,
            "confidence": None,
            "reasoning": response,
            "key_factors": [],
        }

        try:
            lines = response.split("\n")
            for line in lines:
                if line.startswith("PROBABILITY:"):
                    prob_str = line.split(":", 1)[1].strip()
                    result["probability"] = float(prob_str)
                elif line.startswith("CONFIDENCE:"):
                    conf_str = line.split(":", 1)[1].strip()
                    result["confidence"] = int(conf_str)
                elif line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()
                    result["reasoning"] = reasoning
                elif line.startswith("KEY_FACTORS:"):
                    factors = line.split(":", 1)[1].strip()
                    result["key_factors"] = [
                        f.strip() for f in factors.split(",") if f.strip()
                    ]

        except (ValueError, IndexError) as e:
            logger.error("prediction_parse_error", error=str(e), response=response[:200])
            raise ValueError(f"Failed to parse LLM prediction response: {e}")

        # Validate required fields were parsed
        if result["probability"] is None or result["confidence"] is None:
            logger.error(
                "prediction_missing_fields",
                has_probability=result["probability"] is not None,
                has_confidence=result["confidence"] is not None,
                response=response[:200]
            )
            raise ValueError("LLM response missing required PROBABILITY or CONFIDENCE fields")

        # Validate ranges
        if not (0 <= result["probability"] <= 1):
            logger.error("invalid_probability", value=result["probability"])
            raise ValueError(f"Invalid probability: {result['probability']} (must be 0-1)")

        if not (1 <= result["confidence"] <= 10):
            logger.error("invalid_confidence", value=result["confidence"])
            raise ValueError(f"Invalid confidence: {result['confidence']} (must be 1-10)")

        return result

    async def analyze_news_relevance(
        self, news_summary: str, market_question: str
    ) -> Dict[str, Any]:
        """Analyze how relevant news is to a market.

        Args:
            news_summary: Summary of news article
            market_question: Market question

        Returns:
            Dict with relevance score and explanation
        """
        messages = [
            {
                "role": "system",
                "content": "You analyze news relevance to prediction markets.",
            },
            {
                "role": "user",
                "content": f"""How relevant is this news to the following market?

Market: {market_question}

News: {news_summary}

Provide:
RELEVANCE: [score 0-1, where 1 is highly relevant]
IMPACT: [positive/negative/neutral/unclear]
EXPLANATION: [brief explanation]""",
            },
        ]

        response = await self.chat_completion(messages, temperature=0.3)
        return self._parse_relevance_response(response)

    def _parse_relevance_response(self, response: str) -> Dict[str, Any]:
        """Parse news relevance analysis.

        Args:
            response: Raw LLM response

        Returns:
            Parsed relevance dict
        """
        result = {"relevance": 0.0, "impact": "unclear", "explanation": response}

        try:
            lines = response.split("\n")
            for line in lines:
                if line.startswith("RELEVANCE:"):
                    score_str = line.split(":", 1)[1].strip()
                    result["relevance"] = float(score_str)
                elif line.startswith("IMPACT:"):
                    result["impact"] = line.split(":", 1)[1].strip().lower()
                elif line.startswith("EXPLANATION:"):
                    result["explanation"] = line.split(":", 1)[1].strip()
        except (ValueError, IndexError) as e:
            logger.warning("relevance_parse_error", error=str(e))

        return result


# Global LLM client instance
llm_client = LLMClient()
