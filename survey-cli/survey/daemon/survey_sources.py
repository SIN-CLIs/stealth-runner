"""
Survey Sources - Connectors for survey reward platforms.

Supported Platforms:
    - Swagbucks
    - Prolific
    - MTurk
    - Survey Router (aggregator)
"""

# ruff: noqa: E501  # CSS selectors / argparse help / log strings — wrapping changes semantics
from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SurveyOffer:
    """Survey offer from a platform."""
    id: str
    platform: str
    title: str
    url: str
    estimated_time_minutes: int
    reward_amount: float
    reward_currency: str = "USD"
    requirements: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None

    @property
    def hourly_rate(self) -> float:
        """Calculate estimated hourly rate."""
        if self.estimated_time_minutes <= 0:
            return 0
        return (self.reward_amount / self.estimated_time_minutes) * 60


@dataclass
class SurveyResult:
    """Result of a survey attempt."""
    offer_id: str
    platform: str
    status: str  # completed, disqualified, abandoned, error
    earnings: float = 0
    time_spent_minutes: float = 0
    disqualification_reason: str | None = None


class SurveySource(ABC):
    """Abstract base class for survey sources."""

    @abstractmethod
    async def login(self, credentials: dict) -> bool:
        """Login to the platform."""
        pass

    @abstractmethod
    async def get_available_surveys(self) -> list[SurveyOffer]:
        """Get list of available surveys."""
        pass

    @abstractmethod
    async def report_completion(self, result: SurveyResult) -> None:
        """Report survey completion to platform."""
        pass

    @abstractmethod
    async def get_balance(self) -> float:
        """Get current account balance."""
        pass


class SwagbucksSource(SurveySource):
    """Swagbucks survey source connector."""

    BASE_URL = "https://www.swagbucks.com"
    API_URL = "https://www.swagbucks.com/api"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)
        self._logged_in = False
        self._session_token: str | None = None

    async def login(self, credentials: dict) -> bool:
        """Login to Swagbucks."""
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/login",
                data={
                    "email": credentials.get("email"),
                    "password": credentials.get("password"),
                },
                follow_redirects=True,
            )

            if "dashboard" in str(response.url):
                self._logged_in = True
                # Extract session token from cookies
                for cookie in response.cookies:
                    if "session" in cookie.name.lower():
                        self._session_token = cookie.value
                        break
                logger.info("Swagbucks login successful")
                return True

            logger.warning("Swagbucks login failed")
            return False

        except Exception as e:
            logger.error(f"Swagbucks login error: {e}")
            return False

    async def get_available_surveys(self) -> list[SurveyOffer]:
        """Get available Swagbucks surveys."""
        if not self._logged_in:
            return []

        offers = []

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/surveys",
                headers={"Cookie": f"session={self._session_token}"},
            )

            # Parse survey offers from HTML
            # This is a simplified example - real implementation would
            # parse the actual Swagbucks survey listing page

            # Pattern matching for survey cards
            survey_pattern = r'data-survey-id="(\d+)".*?data-reward="(\d+)".*?data-time="(\d+)"'
            matches = re.finditer(survey_pattern, response.text, re.DOTALL)

            for match in matches:
                survey_id = match.group(1)
                reward = int(match.group(2))
                time_min = int(match.group(3))

                offers.append(SurveyOffer(
                    id=f"sb_{survey_id}",
                    platform="swagbucks",
                    title=f"Swagbucks Survey #{survey_id}",
                    url=f"{self.BASE_URL}/surveys/router/{survey_id}",
                    estimated_time_minutes=time_min,
                    reward_amount=reward / 100,  # SB to USD
                    reward_currency="USD",
                ))

            logger.info(f"Found {len(offers)} Swagbucks surveys")

        except Exception as e:
            logger.error(f"Error fetching Swagbucks surveys: {e}")

        return offers

    async def report_completion(self, result: SurveyResult) -> None:
        """Report survey completion."""
        logger.info(f"Swagbucks survey {result.offer_id}: {result.status}")

    async def get_balance(self) -> float:
        """Get Swagbucks balance in USD."""
        if not self._logged_in:
            return 0

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/account/summary",
                headers={"Cookie": f"session={self._session_token}"},
            )

            # Parse balance from page
            balance_match = re.search(r'class="balance"[^>]*>(\d+)', response.text)
            if balance_match:
                sb_balance = int(balance_match.group(1))
                return sb_balance / 100  # Convert SB to USD

        except Exception as e:
            logger.error(f"Error getting Swagbucks balance: {e}")

        return 0


class ProlificSource(SurveySource):
    """Prolific survey source connector."""

    BASE_URL = "https://app.prolific.com"
    API_URL = "https://api.prolific.com"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)
        self._logged_in = False
        self._auth_token: str | None = None

    async def login(self, credentials: dict) -> bool:
        """Login to Prolific."""
        try:
            response = await self.client.post(
                f"{self.API_URL}/auth/login",
                json={
                    "email": credentials.get("email"),
                    "password": credentials.get("password"),
                },
            )

            if response.status_code == 200:
                data = response.json()
                self._auth_token = data.get("access_token")
                self._logged_in = True
                logger.info("Prolific login successful")
                return True

            logger.warning("Prolific login failed")
            return False

        except Exception as e:
            logger.error(f"Prolific login error: {e}")
            return False

    async def get_available_surveys(self) -> list[SurveyOffer]:
        """Get available Prolific studies."""
        if not self._logged_in:
            return []

        offers = []

        try:
            response = await self.client.get(
                f"{self.API_URL}/participant/studies",
                headers={"Authorization": f"Bearer {self._auth_token}"},
            )

            if response.status_code == 200:
                studies = response.json().get("results", [])

                for study in studies:
                    offers.append(SurveyOffer(
                        id=f"prolific_{study['id']}",
                        platform="prolific",
                        title=study.get("name", "Prolific Study"),
                        url=study.get("study_url", ""),
                        estimated_time_minutes=study.get("estimated_completion_time", 10),
                        reward_amount=study.get("reward", 0) / 100,
                        reward_currency=study.get("currency", "GBP"),
                        requirements=study.get("eligibility_requirements", {}),
                    ))

            logger.info(f"Found {len(offers)} Prolific studies")

        except Exception as e:
            logger.error(f"Error fetching Prolific studies: {e}")

        return offers

    async def report_completion(self, result: SurveyResult) -> None:
        """Report study completion."""
        # Prolific handles this automatically via completion URL
        logger.info(f"Prolific study {result.offer_id}: {result.status}")

    async def get_balance(self) -> float:
        """Get Prolific balance."""
        if not self._logged_in:
            return 0

        try:
            response = await self.client.get(
                f"{self.API_URL}/participant/balance",
                headers={"Authorization": f"Bearer {self._auth_token}"},
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("balance", 0) / 100

        except Exception as e:
            logger.error(f"Error getting Prolific balance: {e}")

        return 0


class MTurkSource(SurveySource):
    """Amazon Mechanical Turk source connector."""

    BASE_URL = "https://worker.mturk.com"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)
        self._logged_in = False

    async def login(self, credentials: dict) -> bool:
        """Login to MTurk (via Amazon)."""
        # MTurk login is complex due to Amazon auth
        # This is a placeholder for actual implementation
        logger.warning("MTurk login not fully implemented")
        return False

    async def get_available_surveys(self) -> list[SurveyOffer]:
        """Get available HITs."""
        return []

    async def report_completion(self, result: SurveyResult) -> None:
        """Report HIT completion."""
        pass

    async def get_balance(self) -> float:
        """Get MTurk balance."""
        return 0


class SurveyRouter:
    """
    Survey aggregator that selects best surveys across platforms.

    Optimizes for highest hourly rate while respecting constraints.
    """

    def __init__(self):
        self.sources: dict[str, SurveySource] = {}
        self._blacklist: set[str] = set()
        self._completed_today: list[SurveyResult] = []

    def add_source(self, name: str, source: SurveySource) -> None:
        """Add survey source."""
        self.sources[name] = source
        logger.info(f"Added survey source: {name}")

    def remove_source(self, name: str) -> None:
        """Remove survey source."""
        self.sources.pop(name, None)

    def blacklist_survey(self, survey_id: str) -> None:
        """Blacklist a survey (won't be returned)."""
        self._blacklist.add(survey_id)

    async def get_best_surveys(
        self,
        min_hourly_rate: float = 5.0,
        max_time_minutes: int = 30,
        limit: int = 10,
    ) -> list[SurveyOffer]:
        """
        Get best available surveys sorted by hourly rate.

        Args:
            min_hourly_rate: Minimum acceptable hourly rate
            max_time_minutes: Maximum survey length
            limit: Maximum number of surveys to return
        """
        all_offers = []

        # Fetch from all sources in parallel
        tasks = [
            source.get_available_surveys()
            for source in self.sources.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_offers.extend(result)

        # Filter offers
        filtered = [
            offer for offer in all_offers
            if offer.id not in self._blacklist
            and offer.hourly_rate >= min_hourly_rate
            and offer.estimated_time_minutes <= max_time_minutes
        ]

        # Sort by hourly rate (highest first)
        filtered.sort(key=lambda x: x.hourly_rate, reverse=True)

        logger.info(f"Router found {len(filtered)} qualifying surveys from {len(all_offers)} total")

        return filtered[:limit]

    async def record_result(self, result: SurveyResult) -> None:
        """Record survey completion result."""
        self._completed_today.append(result)

        # Report to platform
        source = self.sources.get(result.platform)
        if source:
            await source.report_completion(result)

        # Blacklist if disqualified too quickly
        if result.status == "disqualified" and result.time_spent_minutes < 1:
            self.blacklist_survey(result.offer_id)
            logger.info(f"Blacklisted quick-DQ survey: {result.offer_id}")

    def get_daily_stats(self) -> dict:
        """Get today's completion statistics."""
        completed = [r for r in self._completed_today if r.status == "completed"]
        disqualified = [r for r in self._completed_today if r.status == "disqualified"]

        total_earnings = sum(r.earnings for r in completed)
        total_time = sum(r.time_spent_minutes for r in self._completed_today)

        return {
            "total_attempts": len(self._completed_today),
            "completed": len(completed),
            "disqualified": len(disqualified),
            "completion_rate": len(completed) / len(self._completed_today) if self._completed_today else 0,
            "total_earnings": total_earnings,
            "total_time_minutes": total_time,
            "effective_hourly_rate": (total_earnings / total_time * 60) if total_time > 0 else 0,
        }

    async def get_total_balance(self) -> dict[str, float]:
        """Get balance from all platforms."""
        balances = {}

        for name, source in self.sources.items():
            try:
                balance = await source.get_balance()
                balances[name] = balance
            except Exception as e:
                logger.warning(f"Error getting {name} balance: {e}")
                balances[name] = 0

        return balances
