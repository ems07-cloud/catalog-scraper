from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Product:
    url: str
    title: str
    category: str
    price: float          # в валюте сайта
    currency: str
    stock: int            # штук в наличии, 0 — нет
    rating: int           # 0–5
    upc: str              # артикул — по нему сравниваем запуски
    description: str = ""
    image_url: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Change:
    kind: str             # new | removed | price | stock_out | stock_back
    upc: str
    title: str
    url: str
    old: float | int | None = None
    new: float | int | None = None

    @property
    def label(self) -> str:
        return {
            "new": "Новый товар",
            "removed": "Пропал из каталога",
            "price": "Цена выросла" if (self.new or 0) > (self.old or 0) else "Цена снизилась",
            "stock_out": "Закончился",
            "stock_back": "Снова в наличии",
        }[self.kind]
