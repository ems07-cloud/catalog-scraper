"""Обход каталога: страницы списка по порядку, карточки товаров — параллельно."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from .fetch import Fetcher
from .models import Product
from .parse import ParseError, parse_listing, parse_product

log = logging.getLogger(__name__)


async def crawl(start_url: str, fetcher: Fetcher, max_pages: int | None = None, limit: int | None = None,
                progress: Callable[[str, int, int], None] | None = None) -> list[Product]:
    # 1) собираем ссылки на товары, идя по «следующей странице»
    links: list[str] = []
    url, pages = start_url, 0
    while url and (max_pages is None or pages < max_pages):
        html = await fetcher.get(url)
        if html is None:
            break
        page_links, url = parse_listing(html, url)
        links.extend(page_links)
        pages += 1
        if progress:
            progress("pages", pages, len(links))
        if limit and len(links) >= limit:
            break
    links = list(dict.fromkeys(links))[:limit] if limit else list(dict.fromkeys(links))

    # 2) карточки товаров параллельно (Fetcher сам держит лимит одновременных запросов)
    done = 0
    products: list[Product] = []

    async def one(link: str) -> None:
        nonlocal done
        html = await fetcher.get(link)
        if html is not None:
            try:
                products.append(parse_product(html, link))
            except ParseError as exc:
                log.warning("%s", exc)
        done += 1
        if progress:
            progress("products", done, len(links))

    await asyncio.gather(*(one(link) for link in links))
    order = {link: i for i, link in enumerate(links)}
    products.sort(key=lambda p: order.get(p.url, 0))
    return products
