"""
Captcha Solver - Multi-provider captcha solving integration.

Supported:
    - reCAPTCHA v2/v3
    - hCaptcha
    - FunCaptcha/Arkose Labs
    - Image-based captcha
    
Providers:
    - 2captcha
    - anti-captcha
    - capmonster
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CaptchaType(str, Enum):
    """Supported captcha types."""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    FUNCAPTCHA = "funcaptcha"
    IMAGE = "image"
    AUDIO = "audio"


@dataclass
class CaptchaTask:
    """Captcha solving task."""
    type: CaptchaType
    site_key: str
    page_url: str
    data_s: str | None = None  # reCAPTCHA data-s parameter
    action: str | None = None   # reCAPTCHA v3 action
    min_score: float = 0.3      # reCAPTCHA v3 minimum score
    image_base64: str | None = None  # For image captchas


@dataclass
class CaptchaResult:
    """Captcha solving result."""
    success: bool
    token: str | None = None
    error: str | None = None
    solve_time: float = 0.0
    cost: float = 0.0


class CaptchaSolver(ABC):
    """Abstract base class for captcha solvers."""
    
    @abstractmethod
    async def solve(self, task: CaptchaTask) -> CaptchaResult:
        """Solve a captcha task."""
        pass
    
    @abstractmethod
    async def get_balance(self) -> float:
        """Get account balance."""
        pass


class TwoCaptchaSolver(CaptchaSolver):
    """2captcha.com solver implementation."""
    
    BASE_URL = "https://2captcha.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=120)
    
    async def solve(self, task: CaptchaTask) -> CaptchaResult:
        """Solve captcha via 2captcha API."""
        start_time = time.time()
        
        try:
            # Create task
            task_id = await self._create_task(task)
            if not task_id:
                return CaptchaResult(success=False, error="Failed to create task")
            
            # Poll for result
            token = await self._get_result(task_id)
            
            solve_time = time.time() - start_time
            
            if token:
                logger.info(f"Captcha solved in {solve_time:.1f}s")
                return CaptchaResult(
                    success=True,
                    token=token,
                    solve_time=solve_time,
                    cost=self._get_cost(task.type),
                )
            else:
                return CaptchaResult(success=False, error="Timeout waiting for solution")
                
        except Exception as e:
            logger.exception(f"Captcha solve error: {e}")
            return CaptchaResult(success=False, error=str(e))
    
    async def _create_task(self, task: CaptchaTask) -> str | None:
        """Create captcha task and return task ID."""
        params: dict[str, Any] = {
            "key": self.api_key,
            "json": 1,
        }
        
        if task.type == CaptchaType.RECAPTCHA_V2:
            params.update({
                "method": "userrecaptcha",
                "googlekey": task.site_key,
                "pageurl": task.page_url,
            })
            if task.data_s:
                params["data-s"] = task.data_s
                
        elif task.type == CaptchaType.RECAPTCHA_V3:
            params.update({
                "method": "userrecaptcha",
                "version": "v3",
                "googlekey": task.site_key,
                "pageurl": task.page_url,
                "action": task.action or "verify",
                "min_score": task.min_score,
            })
            
        elif task.type == CaptchaType.HCAPTCHA:
            params.update({
                "method": "hcaptcha",
                "sitekey": task.site_key,
                "pageurl": task.page_url,
            })
            
        elif task.type == CaptchaType.FUNCAPTCHA:
            params.update({
                "method": "funcaptcha",
                "publickey": task.site_key,
                "pageurl": task.page_url,
            })
            
        elif task.type == CaptchaType.IMAGE:
            params.update({
                "method": "base64",
                "body": task.image_base64,
            })
        
        response = await self.client.post(f"{self.BASE_URL}/in.php", data=params)
        data = response.json()
        
        if data.get("status") == 1:
            return data.get("request")
        
        logger.error(f"2captcha create task error: {data}")
        return None
    
    async def _get_result(self, task_id: str, max_attempts: int = 60) -> str | None:
        """Poll for captcha result."""
        for _ in range(max_attempts):
            await asyncio.sleep(5)
            
            response = await self.client.get(
                f"{self.BASE_URL}/res.php",
                params={
                    "key": self.api_key,
                    "action": "get",
                    "id": task_id,
                    "json": 1,
                }
            )
            data = response.json()
            
            if data.get("status") == 1:
                return data.get("request")
            
            if data.get("request") != "CAPCHA_NOT_READY":
                logger.error(f"2captcha result error: {data}")
                return None
        
        return None
    
    async def get_balance(self) -> float:
        """Get account balance."""
        response = await self.client.get(
            f"{self.BASE_URL}/res.php",
            params={
                "key": self.api_key,
                "action": "getbalance",
                "json": 1,
            }
        )
        data = response.json()
        return float(data.get("request", 0))
    
    def _get_cost(self, captcha_type: CaptchaType) -> float:
        """Get estimated cost per captcha type."""
        costs = {
            CaptchaType.RECAPTCHA_V2: 0.003,
            CaptchaType.RECAPTCHA_V3: 0.003,
            CaptchaType.HCAPTCHA: 0.003,
            CaptchaType.FUNCAPTCHA: 0.003,
            CaptchaType.IMAGE: 0.001,
        }
        return costs.get(captcha_type, 0.003)


class AntiCaptchaSolver(CaptchaSolver):
    """anti-captcha.com solver implementation."""
    
    BASE_URL = "https://api.anti-captcha.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=120)
    
    async def solve(self, task: CaptchaTask) -> CaptchaResult:
        """Solve captcha via anti-captcha API."""
        start_time = time.time()
        
        try:
            # Create task
            task_payload = self._build_task_payload(task)
            
            response = await self.client.post(
                f"{self.BASE_URL}/createTask",
                json={
                    "clientKey": self.api_key,
                    "task": task_payload,
                }
            )
            data = response.json()
            
            if data.get("errorId") != 0:
                return CaptchaResult(success=False, error=data.get("errorDescription"))
            
            task_id = data.get("taskId")
            
            # Poll for result
            token = await self._get_result(task_id)
            solve_time = time.time() - start_time
            
            if token:
                return CaptchaResult(
                    success=True,
                    token=token,
                    solve_time=solve_time,
                )
            else:
                return CaptchaResult(success=False, error="Timeout")
                
        except Exception as e:
            return CaptchaResult(success=False, error=str(e))
    
    def _build_task_payload(self, task: CaptchaTask) -> dict:
        """Build anti-captcha task payload."""
        if task.type == CaptchaType.RECAPTCHA_V2:
            return {
                "type": "RecaptchaV2TaskProxyless",
                "websiteURL": task.page_url,
                "websiteKey": task.site_key,
            }
        elif task.type == CaptchaType.RECAPTCHA_V3:
            return {
                "type": "RecaptchaV3TaskProxyless",
                "websiteURL": task.page_url,
                "websiteKey": task.site_key,
                "minScore": task.min_score,
                "pageAction": task.action or "verify",
            }
        elif task.type == CaptchaType.HCAPTCHA:
            return {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": task.page_url,
                "websiteKey": task.site_key,
            }
        elif task.type == CaptchaType.IMAGE:
            return {
                "type": "ImageToTextTask",
                "body": task.image_base64,
            }
        else:
            raise ValueError(f"Unsupported captcha type: {task.type}")
    
    async def _get_result(self, task_id: int, max_attempts: int = 60) -> str | None:
        """Poll for captcha result."""
        for _ in range(max_attempts):
            await asyncio.sleep(5)
            
            response = await self.client.post(
                f"{self.BASE_URL}/getTaskResult",
                json={
                    "clientKey": self.api_key,
                    "taskId": task_id,
                }
            )
            data = response.json()
            
            if data.get("status") == "ready":
                solution = data.get("solution", {})
                return (
                    solution.get("gRecaptchaResponse") or
                    solution.get("token") or
                    solution.get("text")
                )
            
            if data.get("errorId") != 0:
                return None
        
        return None
    
    async def get_balance(self) -> float:
        """Get account balance."""
        response = await self.client.post(
            f"{self.BASE_URL}/getBalance",
            json={"clientKey": self.api_key}
        )
        data = response.json()
        return data.get("balance", 0)


class CaptchaSolverFactory:
    """Factory for creating captcha solvers."""
    
    @staticmethod
    def create(provider: str, api_key: str) -> CaptchaSolver:
        """Create a captcha solver for the given provider."""
        providers = {
            "2captcha": TwoCaptchaSolver,
            "anti-captcha": AntiCaptchaSolver,
        }
        
        solver_class = providers.get(provider.lower())
        if not solver_class:
            raise ValueError(f"Unknown captcha provider: {provider}")
        
        return solver_class(api_key)


class CaptchaSolverQueue:
    """Queue-based captcha solver with retry and fallback."""
    
    def __init__(
        self,
        primary_provider: str,
        primary_api_key: str,
        fallback_provider: str | None = None,
        fallback_api_key: str | None = None,
        max_retries: int = 3,
    ):
        self.primary = CaptchaSolverFactory.create(primary_provider, primary_api_key)
        self.fallback = None
        if fallback_provider and fallback_api_key:
            self.fallback = CaptchaSolverFactory.create(fallback_provider, fallback_api_key)
        self.max_retries = max_retries
    
    async def solve(self, task: CaptchaTask) -> CaptchaResult:
        """Solve captcha with retry and fallback logic."""
        last_error = None
        
        # Try primary solver
        for attempt in range(self.max_retries):
            result = await self.primary.solve(task)
            if result.success:
                return result
            last_error = result.error
            logger.warning(f"Primary solver attempt {attempt + 1} failed: {last_error}")
        
        # Try fallback solver
        if self.fallback:
            logger.info("Switching to fallback captcha solver")
            for attempt in range(self.max_retries):
                result = await self.fallback.solve(task)
                if result.success:
                    return result
                last_error = result.error
                logger.warning(f"Fallback solver attempt {attempt + 1} failed: {last_error}")
        
        return CaptchaResult(success=False, error=f"All solvers failed: {last_error}")
