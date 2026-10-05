"""Загрузка и обход без сети: сайт подменён через httpx.MockTransport."""
import asyncio
from pathlib import Path

import httpx

from scraper.crawler import crawl
from scraper.fetch import Fetcher

FIX = Path(__file__).parent / "fixtures"
BASE = "https://books.toscrape.com/"


def fetcher(handler, **kw):
    return Fetcher(transport=httpx.MockTransport(handler), delay=0, backoff=0, **kw)


def run(coro):
    return asyncio.run(coro)


def test_temporary_errors_are_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, text="ok")

    f = fetcher(handler)
    assert run(f.get(BASE)) == "ok"
    assert (f.stats.requests, f.stats.retries, f.stats.failed) == (3, 2, [])


def test_not_found_is_not_retried():
    f = fetcher(lambda r: httpx.Response(404))
    assert run(f.get(BASE + "nope")) is None
    assert f.stats.requests == 1 and f.stats.failed == [BASE + "nope"]


def test_network_error_gives_up_after_retries():
    def handler(request):
        raise httpx.ConnectError("нет сети", request=request)

    f = fetcher(handler, retries=2)
    assert run(f.get(BASE)) is None
    assert f.stats.requests == 3 and f.stats.retries == 2


def site(request):
    """Мини-копия сайта: две страницы списка и одна карточка на все ссылки."""
    path = request.url.path
    if path in ("/", "/index.html"):
        return httpx.Response(200, text=(FIX / "listing_page1.html").read_text(encoding="utf-8"))
    if path == "/catalogue/page-2.html":
        html = (FIX / "listing_page2.html").read_text(encoding="utf-8").replace('class="next"', 'class="x"')
        return httpx.Response(200, text=html)
    if path.endswith("/index.html") and path.startswith("/catalogue/"):
        if "in-her-wake" in path:
            return httpx.Response(500)        # одна карточка «падает» — обход не должен сломаться
        return httpx.Response(200, text=(FIX / "product.html").read_text(encoding="utf-8"))
    return httpx.Response(404)


def test_crawl_follows_pages_and_survives_broken_card():
    f = fetcher(site, retries=1)
    seen = []
    products = run(crawl(BASE, f, progress=lambda stage, done, total: seen.append(stage)))
    assert len(products) == 39                 # 40 ссылок, одна карточка отдаёт 500
    assert f.stats.failed == [BASE + "catalogue/in-her-wake_980/index.html"]
    assert "pages" in seen and "products" in seen


def test_crawl_respects_page_and_item_limits():
    assert len(run(crawl(BASE, fetcher(site), max_pages=1))) == 20
    assert len(run(crawl(BASE, fetcher(site), limit=5))) == 5
