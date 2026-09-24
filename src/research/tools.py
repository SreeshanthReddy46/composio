import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import httpx
import trafilatura
from tenacity import retry, stop_after_attempt, wait_exponential

from src.research.config import settings

logger = logging.getLogger(__name__)


def get_cache_key(url: str, prompt: str = "") -> str:
    combined = f"{url.strip()}::{prompt.strip()}".encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


class DiskCache:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or settings.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[dict]:
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Cache read error for {key}: {e}")
        return None

    def set(self, key: str, data: dict) -> None:
        path = self.cache_dir / f"{key}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Cache write error for {key}: {e}")


cache = DiskCache()


class ComposioSessionManager:
    """Manages Composio v3 SDK session for tool execution."""
    def __init__(self, user_id: str = "research_agent"):
        self.user_id = user_id
        self._session = None
        self._composio = None

    def get_session(self):
        if self._session is None and settings.COMPOSIO_API_KEY:
            try:
                from composio import Composio
                self._composio = Composio(api_key=settings.COMPOSIO_API_KEY)
                self._session = self._composio.create(user_id=self.user_id)
                logger.info(f"Initialized Composio session for user {self.user_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize Composio session: {e}")
        return self._session


session_manager = ComposioSessionManager()


async def fetch_page_trafilatura(client: httpx.AsyncClient, url: str) -> Tuple[int, str]:
    """Fetch URL with httpx and extract readable content via Trafilatura."""
    headers = {"User-Agent": settings.USER_AGENT}
    try:
        response = await client.get(
            url,
            headers=headers,
            follow_redirects=True,
            timeout=settings.REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            text = trafilatura.extract(response.text, include_links=True, include_tables=True) or response.text
            return 200, text
        return response.status_code, f"HTTP Error {response.status_code}"
    except Exception as e:
        logger.debug(f"Trafilatura fetch failed for {url}: {e}")
        return 0, str(e)


async def fetch_page_jina(client: httpx.AsyncClient, url: str) -> Tuple[int, str]:
    """Fallback fetcher using Jina Reader API (https://r.jina.ai/)."""
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "User-Agent": settings.USER_AGENT,
        "Accept": "text/plain",
        "X-Return-Format": "markdown",
    }
    try:
        response = await client.get(
            jina_url,
            headers=headers,
            follow_redirects=True,
            timeout=settings.REQUEST_TIMEOUT,
        )
        if response.status_code == 200 and response.text.strip():
            return 200, response.text
        return response.status_code, f"Jina Reader returned {response.status_code}"
    except Exception as e:
        logger.debug(f"Jina Reader fetch failed for {url}: {e}")
        return 0, str(e)


async def fetch_page_playwright(url: str) -> Tuple[int, str]:
    """Fallback fetcher using Playwright for JavaScript-heavy pages."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=settings.USER_AGENT)
            response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            status = response.status if response else 200
            content = await page.content()
            await browser.close()
            text = trafilatura.extract(content, include_links=True) or content
            return status, text
    except Exception as e:
        logger.debug(f"Playwright fetch failed for {url}: {e}")
        return 0, str(e)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=False)
async def fetch_url_with_fallbacks(client: httpx.AsyncClient, url: str) -> Tuple[int, str]:
    """Tiered fetch: Cache -> Trafilatura -> Jina Reader -> Playwright."""
    cache_key = get_cache_key(url)
    cached = cache.get(cache_key)
    if cached:
        return cached.get("status_code", 200), cached.get("text", "")

    # 1. Primary: Trafilatura
    status, text = await fetch_page_trafilatura(client, url)
    
    # Check if text is too thin (e.g. JS hydration blocker)
    if status != 200 or len(text.strip()) < 150:
        logger.info(f"Primary fetch insufficient for {url} (status={status}, len={len(text)}). Trying Jina Reader...")
        jina_status, jina_text = await fetch_page_jina(client, url)
        if jina_status == 200 and len(jina_text.strip()) > 150:
            status, text = jina_status, jina_text
        else:
            # 3. Fallback to Playwright
            logger.info(f"Jina fetch insufficient for {url}. Trying Playwright...")
            pw_status, pw_text = await fetch_page_playwright(url)
            if pw_status == 200 and len(pw_text.strip()) > 150:
                status, text = pw_status, pw_text

    if status == 200:
        cache.set(cache_key, {"status_code": status, "text": text, "url": url})

    return status, text
