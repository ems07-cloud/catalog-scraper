"""История запусков в SQLite: каждый запуск — срез каталога; сравнение со срезом прошлого запуска."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Change, Product

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, started_at TEXT, source TEXT, products INTEGER);
CREATE TABLE IF NOT EXISTS snapshot (
    run_id INTEGER, upc TEXT, title TEXT, url TEXT, category TEXT, price REAL, stock INTEGER,
    PRIMARY KEY (run_id, upc));
"""


class History:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    def last_snapshot(self, source: str) -> dict[str, dict]:
        row = self.db.execute("SELECT id FROM runs WHERE source = ? ORDER BY id DESC LIMIT 1", (source,)).fetchone()
        if not row:
            return {}
        cur = self.db.execute("SELECT upc, title, url, price, stock FROM snapshot WHERE run_id = ?", (row[0],))
        return {r[0]: {"title": r[1], "url": r[2], "price": r[3], "stock": r[4]} for r in cur}

    def save(self, source: str, products: list[Product]) -> int:
        cur = self.db.execute("INSERT INTO runs (started_at, source, products) VALUES (?, ?, ?)",
                              (datetime.now().isoformat(timespec="seconds"), source, len(products)))
        run_id = cur.lastrowid
        self.db.executemany(
            "INSERT OR REPLACE INTO snapshot VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(run_id, p.upc, p.title, p.url, p.category, p.price, p.stock) for p in products if p.upc])
        self.db.commit()
        return run_id

    def close(self) -> None:
        self.db.close()


def diff(previous: dict[str, dict], products: list[Product]) -> list[Change]:
    """Что изменилось с прошлого запуска. Первый запуск — изменений нет (не с чем сравнивать)."""
    if not previous:
        return []
    changes: list[Change] = []
    current = {p.upc: p for p in products if p.upc}
    for upc, p in current.items():
        old = previous.get(upc)
        if old is None:
            changes.append(Change("new", upc, p.title, p.url, None, p.price))
            continue
        if round(old["price"], 2) != round(p.price, 2):
            changes.append(Change("price", upc, p.title, p.url, old["price"], p.price))
        if old["stock"] > 0 and p.stock == 0:
            changes.append(Change("stock_out", upc, p.title, p.url, old["stock"], 0))
        elif old["stock"] == 0 and p.stock > 0:
            changes.append(Change("stock_back", upc, p.title, p.url, 0, p.stock))
    for upc, old in previous.items():
        if upc not in current:
            changes.append(Change("removed", upc, old["title"], old["url"], old["price"], None))
    return changes
