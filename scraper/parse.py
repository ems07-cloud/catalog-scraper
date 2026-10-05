"""Разбор страниц каталога. Только HTML → данные, без сети: так это проверяется тестами."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .models import Product

RATING = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


class ParseError(ValueError):
    pass


def _text(node) -> str:
    return " ".join(node.text().split()) if node else ""


def parse_listing(html: str, page_url: str) -> tuple[list[str], str | None]:
    """Ссылки на товары со страницы списка и адрес следующей страницы (или None)."""
    tree = HTMLParser(html)
    links = [urljoin(page_url, a.attributes["href"])
             for a in tree.css("article.product_pod h3 a") if a.attributes.get("href")]
    nxt = tree.css_first("li.next a")
    return links, (urljoin(page_url, nxt.attributes["href"]) if nxt else None)


def parse_money(text: str) -> tuple[float, str]:
    m = re.search(r"([^\d\s.,]*)\s*([\d\s.,]+)", text or "")
    if not m:
        raise ParseError(f"не разобрать цену: {text!r}")
    currency, number = m.group(1) or "", m.group(2).replace(" ", "").replace(",", ".")
    return round(float(number), 2), currency


def parse_stock(text: str) -> int:
    """«In stock (22 available)» → 22, «Out of stock» → 0."""
    if not text or "out of stock" in text.lower():
        return 0
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else 1


def parse_product(html: str, url: str) -> Product:
    tree = HTMLParser(html)
    main = tree.css_first("div.product_main")
    if main is None:
        raise ParseError(f"на странице нет карточки товара: {url}")

    table = {_text(row.css_first("th")): _text(row.css_first("td")) for row in tree.css("table.table tr")}
    price, currency = parse_money(_text(main.css_first("p.price_color")))
    rating_node = main.css_first("p.star-rating")
    rating = 0
    if rating_node:
        classes = (rating_node.attributes.get("class") or "").split()
        rating = next((RATING[c] for c in classes if c in RATING), 0)

    crumbs = [_text(li) for li in tree.css("ul.breadcrumb li")]
    category = crumbs[-2] if len(crumbs) >= 3 else ""
    description = _text(tree.css_first("#product_description ~ p"))   # абзац сразу после заголовка
    img = tree.css_first("div.item.active img") or tree.css_first("#product_gallery img")

    return Product(
        url=url,
        title=_text(main.css_first("h1")),
        category=category,
        price=price,
        currency=currency,
        stock=parse_stock(table.get("Availability") or _text(main.css_first("p.availability"))),
        rating=rating,
        upc=table.get("UPC", ""),
        description=description,
        image_url=urljoin(url, img.attributes.get("src", "")) if img else "",
    )
