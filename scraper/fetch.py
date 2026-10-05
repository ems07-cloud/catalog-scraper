"""Загрузка страниц: ограничение параллельности, пауза между запросами, повторы с нарастающей паузой."""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass
class FetchStats:
    requests: int = 0
    retries: int = 0
    failed: list[str] = field(default_factory=list)


class Fetcher:
    def __init__(self, concurrency: int = 8, delay: float = 0.1, retries: int = 3, timeout: float = 20,
                 backoff: float = 0.5, transport: httpx.AsyncBaseTransport | None = None):
        self.sem = asyncio.Semaphore(concurrency)
        self.delay, self.retries, self.backoff = delay, retries, backoff
        self.stats = FetchStats()
        self.client = httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, transport=transport,
            headers={"User-Agent": "catalog-scraper/1.0 (+https://github.com/ems07-cloud/catalog-scraper)"})

    async def get(self, url: str) -> str | None:
        """HTML страницы или None, если не удалось после всех попыток."""
        async with self.sem:
            for attempt in range(self.retries + 1):
                try:
                    self.stats.requests += 1
                    resp = await self.client.get(url)
                    if resp.status_code in RETRY_STATUSES:
                        raise httpx.HTTPStatusError(f"{resp.status_code}", request=resp.request, response=resp)
                    if resp.status_code >= 400:           # 404 и т. п. — повторять бесполезно
                        log.warning("%s: %s", url, resp.status_code)
                        self.stats.failed.append(url)
                        return None
                    await asyncio.sleep(self.delay)        # вежливо к сайту
                    return resp.text
                except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                    if attempt == self.retries:
                        log.warning("%s: не удалось после %s попыток (%s)", url, attempt + 1, exc)
                        self.stats.failed.append(url)
                        return None
                    self.stats.retries += 1
                    await asyncio.sleep((2 ** attempt) * self.backoff + random.random() * self.backoff * 0.6)
        return None

    async def close(self) -> None:
        await self.client.aclose()
