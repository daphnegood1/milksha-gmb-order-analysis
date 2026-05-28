from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fetch_official_stores import make_summary, write_outputs


DATA_PATH = Path("data/stores.json")
API_BASE = "https://loctw-service-api.nidin.shop/shopper/v2"
CHECKED_AT = date.today().isoformat()


def fetch_json(path: str, params: dict) -> dict:
    url = f"{API_BASE}{path}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://milksha.nidin.shop",
            "Referer": "https://milksha.nidin.shop/",
        },
    )
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize(value: str) -> str:
    value = (value or "").replace("臺", "台").replace("巿", "市")
    value = value.replace("❄️", "").replace("❄", "")
    value = re.sub(r"^Milksha\s*Plus\s*", "", value, flags=re.I)
    value = re.sub(r"^\d{3,6}", "", value)
    value = re.sub(r"\s+", "", value)
    value = value.replace("一樓", "1樓")
    return value.lower()


def phone_key(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-7:] if len(digits) >= 7 else digits


def fetch_nidin_stores() -> list[dict]:
    first = fetch_json("/store/listByDefault", {"brand_code": "milkshoptea", "page": 1, "count": 1})
    total = int(first["meta"]["total_amount"])
    page_size = 20
    stores: list[dict] = []
    for page in range(1, (total + page_size - 1) // page_size + 1):
        payload = fetch_json("/store/listByDefault", {"brand_code": "milkshoptea", "page": page, "count": page_size})
        stores.extend(payload.get("list", []))
    return stores


def build_match_indexes(nidin_stores: list[dict]) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    by_name: dict[str, dict] = {}
    by_phone: dict[str, dict] = {}
    by_address: dict[str, dict] = {}
    for item in nidin_stores:
        by_name[normalize(item.get("name", ""))] = item
        if item.get("name_short"):
            by_name[normalize(item["name_short"])] = item
        if phone_key(item.get("tel", "")):
            by_phone[phone_key(item.get("tel", ""))] = item
        address = normalize(item.get("address", ""))
        if address:
            by_address[address] = item
    return by_name, by_phone, by_address


def match_store(store: dict, indexes: tuple[dict[str, dict], dict[str, dict], dict[str, dict]]) -> dict | None:
    by_name, by_phone, by_address = indexes
    name = normalize(store["storeName"])
    phone = phone_key(store.get("phone", ""))
    address = normalize(store.get("address", ""))

    if phone and phone in by_phone:
        return by_phone[phone]
    if name in by_name:
        return by_name[name]
    for nidin_address, item in by_address.items():
        if address and (address in nidin_address or nidin_address in address):
            return item
    return None


def add_unique(values: list[str], provider: str) -> list[str]:
    return values if provider in values else [*values, provider]


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    stores = payload["stores"]
    nidin_stores = fetch_nidin_stores()
    indexes = build_match_indexes(nidin_stores)

    matched = 0
    for store in stores:
        item = match_store(store, indexes)
        if not item:
            store["nidinOrderStatus"] = "not_found"
            continue

        matched += 1
        store["nidinOrderStatus"] = "confirmed"
        store["nidinStoreId"] = item["id"]
        store["nidinOrderUrl"] = f"https://milksha.nidin.shop/menu/{item['id']}"
        store["takeoutAvailable"] = True
        store["takeoutProviders"] = add_unique(store.get("takeoutProviders", []), "Nidin")
        if item.get("delivery_info") or item.get("delivery_way_description"):
            store["deliveryAvailable"] = True
            store["deliveryProviders"] = add_unique(store.get("deliveryProviders", []), "Nidin")
        notes = store.get("evidenceNotes", "")
        nidin_note = (
            f"官方 Nidin 點餐 API 確認此店可線上點餐；"
            f"門市 ID {item['id']}，外送條件：{item.get('delivery_way_description') or '未提供'}。"
        )
        store["evidenceNotes"] = f"{notes} {nidin_note}".strip()
        store["checkedAt"] = CHECKED_AT

    write_outputs(stores)
    summary = make_summary(stores)
    summary["nidinMatchedCount"] = matched
    summary["nidinSource"] = "https://milksha.nidin.shop/"
    Path("data/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
