"""Запуск: python -m scraper --pages 5 --out results/books.xlsx"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from .crawler import crawl
from .export import to_csv, to_xlsx
from .fetch import Fetcher
from .history import History, diff

DEFAULT_URL = "https://books.toscrape.com/"


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="scraper", description="Сбор каталога в Excel с отслеживанием изменений")
    p.add_argument("--url", default=DEFAULT_URL, help="первая страница каталога")
    p.add_argument("--pages", type=int, default=None, help="сколько страниц списка обойти (по умолчанию все)")
    p.add_argument("--limit", type=int, default=None, help="не больше N товаров")
    p.add_argument("--concurrency", type=int, default=8, help="одновременных запросов")
    p.add_argument("--delay", type=float, default=0.1, help="пауза после запроса, сек")
    p.add_argument("--out", default=None, help="файл Excel (по умолчанию results/catalog_<дата>.xlsx)")
    p.add_argument("--csv", action="store_true", help="дополнительно сохранить CSV")
    p.add_argument("--history", default="history.sqlite", help="база истории для сравнения запусков")
    return p.parse_args(argv)


def progress(stage: str, done: int, total: int) -> None:
    if stage == "pages":
        sys.stdout.write(f"\rстраниц каталога: {done}, ссылок на товары: {total}   ")
    else:
        if done == 1:
            sys.stdout.write("\n")
        sys.stdout.write(f"\rкарточек товаров: {done}/{total}   ")
    sys.stdout.flush()


async def run(args) -> int:
    started = time.time()
    fetcher = Fetcher(concurrency=args.concurrency, delay=args.delay)
    try:
        products = await crawl(args.url, fetcher, max_pages=args.pages, limit=args.limit, progress=progress)
    finally:
        await fetcher.close()
    print()

    history = History(args.history)
    changes = diff(history.last_snapshot(args.url), products)
    history.save(args.url, products)
    history.close()

    out = Path(args.out or f"results/catalog_{datetime.now():%Y-%m-%d_%H%M}.xlsx")
    to_xlsx(products, changes, out)
    if args.csv:
        to_csv(products, out.with_suffix(".csv"))

    st = fetcher.stats
    print(f"Готово за {time.time() - started:.0f} с: товаров {len(products)}, "
          f"запросов {st.requests}, повторов {st.retries}, ошибок {len(st.failed)}")
    if changes:
        kinds = {}
        for c in changes:
            kinds[c.label] = kinds.get(c.label, 0) + 1
        print("Изменения с прошлого запуска: " + ", ".join(f"{k} — {v}" for k, v in kinds.items()))
    else:
        print("Изменений с прошлого запуска нет")
    print(f"Excel: {out}")
    return 0 if products else 1


def main(argv=None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
