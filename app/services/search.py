"""店と料理の検索。ひらがなとカタカナ、全角と半角、大文字と小文字の違いを吸収する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.data import db
from app.models import Item, Store
from app.services.stores import StoreStatus, store_status

SEARCH_CATEGORIES: list[tuple[str, str, set[str]]] = [
    ("kebab", "ケバブ", {"kebab"}),
    ("burger", "ハンバーガー", {"burger"}),
    ("japanese", "和食", {"japanese", "gyudon"}),
    ("chinese", "中華", {"chinese"}),
    ("curry", "カレー", {"curry"}),
    ("cvs", "コンビニ・スーパー", {"cvs", "super"}),
]


def normalize(text: str) -> str:
    """比べる前に大文字と小文字をそろえる。"""
    return text.lower().strip()


@dataclass
class StoreHit:
    store: Store
    status: StoreStatus
    menu_text: str


@dataclass
class ItemHit:
    item: Item
    store: Store
    via_description: bool


@dataclass
class SearchResult:
    query: str
    stores: list[StoreHit]
    items: list[ItemHit]


def search(query: str, categories: set[str] | None = None, open_only: bool = False, free_delivery: bool = False,
           within_30: bool = False, sort: str = "relevance") -> SearchResult:
    q = normalize(query)
    allowed: set[str] | None = None
    if categories:
        allowed = set()
        for key, _, cats in SEARCH_CATEGORIES:
            if key in categories:
                allowed |= cats

    def store_ok(store: Store) -> bool:
        if allowed is not None and store.category not in allowed:
            return False
        if open_only and not store_status(store).orderable:
            return False
        if free_delivery and store.free_delivery_from is None:
            return False
        if within_30 and store.eta_max > 30:
            return False
        return True

    stores: list[StoreHit] = []
    items: list[ItemHit] = []
    if q:
        for store in db.stores.values():
            if not store_ok(store):
                continue
            menu = db.items_of(store.id)
            haystack = [store.name, store.category_label, store.area] + [i.name for i in menu]
            if any(q in normalize(h) for h in haystack):
                stores.append(StoreHit(store, store_status(store), "、".join(i.name for i in menu)))
        for item in db.items.values():
            store = db.stores[item.store_id]
            if not store_ok(store):
                continue
            in_name = q in normalize(item.name)
            in_desc = q in normalize(item.description)
            if in_name or in_desc:
                items.append(ItemHit(item, store, via_description=not in_name))
    if sort == "eta":
        stores.sort(key=lambda h: (h.store.eta_min, h.store.eta_max))
        items.sort(key=lambda h: (h.store.eta_min, h.store.eta_max))
    elif sort == "rating":
        stores.sort(key=lambda h: h.store.rating, reverse=True)
        items.sort(key=lambda h: h.store.rating, reverse=True)
    return SearchResult(query, stores, items)
