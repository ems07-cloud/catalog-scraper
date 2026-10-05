from pathlib import Path

import pytest

from scraper.parse import ParseError, parse_listing, parse_money, parse_product, parse_stock

FIX = Path(__file__).parent / "fixtures"
BASE = "https://books.toscrape.com/"


def read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_listing_links_and_next_page():
    links, nxt = parse_listing(read("listing_page1.html"), BASE + "index.html")
    assert len(links) == 20
    assert links[0] == BASE + "catalogue/a-light-in-the-attic_1000/index.html"
    assert nxt == BASE + "catalogue/page-2.html"


def test_relative_links_resolve_from_inner_pages():
    links, nxt = parse_listing(read("listing_page2.html"), BASE + "catalogue/page-2.html")
    assert links[0] == BASE + "catalogue/in-her-wake_980/index.html"
    assert nxt == BASE + "catalogue/page-3.html"


def test_last_page_has_no_next():
    html = read("listing_page1.html").replace('class="next"', 'class="was-next"')
    assert parse_listing(html, BASE)[1] is None


def test_category_page_is_a_listing_too():
    links, _ = parse_listing(read("category_travel.html"), BASE + "catalogue/category/books/travel_2/index.html")
    assert len(links) == 11
    assert all(link.startswith(BASE + "catalogue/") for link in links)


def test_product_card():
    p = parse_product(read("product.html"), BASE + "catalogue/a-light-in-the-attic_1000/index.html")
    assert p.title == "A Light in the Attic"
    assert p.category == "Poetry"
    assert (p.price, p.currency) == (51.77, "£")
    assert p.stock == 22
    assert p.rating == 3
    assert p.upc == "a897fe39b1053632"
    assert p.description.startswith("It's hard to imagine a world without A Light in the Attic")
    assert p.image_url.startswith(BASE + "media/cache/")


def test_non_product_page_is_rejected():
    with pytest.raises(ParseError):
        parse_product(read("listing_page1.html"), BASE)


@pytest.mark.parametrize("text, value", [("£51.77", (51.77, "£")), ("1 299,50 ₽", (1299.5, "")), ("$ 10", (10.0, "$"))],
                         ids=["pound", "rub-comma", "dollar-space"])
def test_money(text, value):
    assert parse_money(text) == value


@pytest.mark.parametrize("text, qty", [("In stock (22 available)", 22), ("Out of stock", 0), ("In stock", 1), ("", 0)],
                         ids=["count", "out", "no-count", "empty"])
def test_stock(text, qty):
    assert parse_stock(text) == qty
