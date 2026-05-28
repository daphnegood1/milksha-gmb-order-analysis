from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


BRAND = "迷客夏"
CHECKED_AT = "2026-05-28"
OFFICIAL_STORE_LIST_URL = "https://www.milksha.com/store_detail.php?uID=1"
PLANNED_SOURCE_URL = "https://www.milksha.com/en/store_detail.php?uID=22"
OUT_DIR = Path("data")

COUNTIES = [
    "臺北市",
    "台北市",
    "新北市",
    "基隆市",
    "桃園市",
    "新竹縣",
    "新竹市",
    "苗栗縣",
    "臺中市",
    "台中市",
    "彰化縣",
    "南投縣",
    "雲林縣",
    "嘉義縣",
    "嘉義市",
    "臺南市",
    "台南市",
    "高雄市",
    "屏東縣",
    "宜蘭縣",
    "花蓮縣",
    "台東縣",
    "臺東縣",
    "金門縣",
    "澎湖縣",
]

DISTRICT_RE = re.compile(r"([^\d\s縣市]{1,8}(?:區|鄉|鎮|市))")


def fetch(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=45) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def clean_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s+", "\n", value)
    return value.strip()


def normalize_county(value: str) -> str:
    return value.replace("台北市", "臺北市").replace("台中市", "臺中市").replace("台南市", "臺南市").replace("台東縣", "臺東縣")


def strip_postal_code(address: str) -> str:
    return re.sub(r"^\s*\d{3,6}\s*", "", address).strip()


def parse_location(address: str) -> tuple[str, str]:
    normalized = normalize_county(strip_postal_code(address))
    county = ""
    for candidate in COUNTIES:
        normalized_candidate = normalize_county(candidate)
        if normalized_candidate in normalized:
            county = normalized_candidate
            break

    district = ""
    if county:
        after_county = normalized.split(county, 1)[1]
        match = DISTRICT_RE.search(after_county)
        if match:
            district = match.group(1)
    return county, district


def maps_search_url(name: str, address: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote(f'{BRAND} {name} {address}')}"


def parse_stores(page: str) -> list[dict]:
    pattern = re.compile(
        r'<div class="store_box">\s*'
        r'<a href="(?P<map_url>[^"]*)"[^>]*>.*?'
        r"<h3>(?P<name>.*?)</h3>\s*"
        r"<p>(?P<address>.*?)</p>\s*"
        r"<ul>\s*<li>(?P<phone>.*?)</li>\s*"
        r"<li>(?P<hours>.*?)</li>",
        re.S,
    )
    stores: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for index, match in enumerate(pattern.finditer(page), start=1):
        name = clean_text(match.group("name")).replace("❄️", "").strip()
        address = clean_text(match.group("address"))
        phone = clean_text(match.group("phone"))
        hours = clean_text(match.group("hours"))
        official_map_url = html.unescape(match.group("map_url")).strip()
        if not name or not address:
            continue
        key = (name, address)
        if key in seen:
            continue
        seen.add(key)
        county, district = parse_location(address)
        gmb_url = official_map_url if official_map_url else maps_search_url(name, address)
        stores.append(
            {
                "brand": BRAND,
                "storeName": name,
                "county": county,
                "district": district,
                "address": address,
                "phone": phone,
                "hours": hours,
                "officialSourceUrl": OFFICIAL_STORE_LIST_URL,
                "officialPlannedSourceUrl": PLANNED_SOURCE_URL,
                "officialMapUrl": official_map_url,
                "gmbUrl": gmb_url,
                "gmbStatus": "confirmed" if official_map_url else "needs_manual_review",
                "takeoutAvailable": None,
                "deliveryAvailable": None,
                "takeoutProviders": [],
                "deliveryProviders": [],
                "otherProviders": [],
                "evidenceNotes": "官方門市頁提供 Google Maps 連結；GMB 點餐外帶/外送服務商仍需逐店人工開啟商家檔案確認。",
                "checkedAt": CHECKED_AT,
                "sourceIndex": index,
            }
        )
    return stores


def apply_manual_verifications(stores: list[dict]) -> None:
    for store in stores:
        normalized_name = store["storeName"].replace("臺", "台")
        normalized_address = store["address"].replace("臺", "台")
        if "台南中華店" in normalized_name or "中華二路195號" in normalized_address:
            store.update(
                {
                    "gmbStatus": "confirmed",
                    "takeoutAvailable": True,
                    "deliveryAvailable": True,
                    "takeoutProviders": ["foodpanda", "Uber Eats"],
                    "deliveryProviders": ["foodpanda", "Uber Eats"],
                    "otherProviders": ["lin.ee"],
                    "evidenceNotes": "使用者提供的永康中華店 GMB 畫面驗證：可記錄 foodpanda、Uber Eats、lin.ee。",
                }
            )


def make_summary(stores: list[dict]) -> dict:
    provider_counts: Counter[str] = Counter()
    takeout_provider_counts: Counter[str] = Counter()
    delivery_provider_counts: Counter[str] = Counter()
    other_provider_counts: Counter[str] = Counter()
    for store in stores:
        for provider in set(store["takeoutProviders"]):
            takeout_provider_counts[provider] += 1
        for provider in set(store["deliveryProviders"]):
            delivery_provider_counts[provider] += 1
        for provider in set(store["otherProviders"]):
            other_provider_counts[provider] += 1
        providers = set(store["takeoutProviders"]) | set(store["deliveryProviders"]) | set(store["otherProviders"])
        for provider in providers:
            provider_counts[provider] += 1
    return {
        "generatedAt": CHECKED_AT,
        "officialStoreCount": len(stores),
        "gmbFoundCount": sum(1 for store in stores if store["gmbStatus"] == "confirmed"),
        "takeoutCount": sum(1 for store in stores if store["takeoutAvailable"] is True),
        "deliveryCount": sum(1 for store in stores if store["deliveryAvailable"] is True),
        "unknownCount": sum(
            1
            for store in stores
            if store["takeoutAvailable"] is None or store["deliveryAvailable"] is None or store["gmbStatus"] != "confirmed"
        ),
        "providerCounts": dict(sorted(provider_counts.items())),
        "takeoutProviderCounts": dict(sorted(takeout_provider_counts.items())),
        "deliveryProviderCounts": dict(sorted(delivery_provider_counts.items())),
        "otherProviderCounts": dict(sorted(other_provider_counts.items())),
        "gmbStatusCounts": dict(Counter(store["gmbStatus"] for store in stores)),
        "source": {
            "officialStoreList": OFFICIAL_STORE_LIST_URL,
            "plannedSourceFromRequest": PLANNED_SOURCE_URL,
            "notes": "uID=22 is the search page. uID=1 is the official Taiwan listing page that renders store cards.",
        },
    }


def make_audit_samples(stores: list[dict]) -> list[dict]:
    samples: list[dict] = []
    seen_counties: set[str] = set()

    preferred = ["臺北市", "新北市", "桃園市", "新竹市", "臺中市", "彰化縣", "嘉義市", "臺南市", "高雄市", "屏東縣"]
    for county in preferred:
        for store in stores:
            if store["county"] == county and county not in seen_counties:
                samples.append(
                    {
                        "storeName": store["storeName"],
                        "county": store["county"],
                        "address": store["address"],
                        "officialMapUrl": store["officialMapUrl"],
                        "gmbUrl": store["gmbUrl"],
                        "checkResult": "official_store_and_map_link_captured",
                        "notes": store["evidenceNotes"],
                        "checkedAt": CHECKED_AT,
                    }
                )
                seen_counties.add(county)
                break
        if len(samples) >= 10:
            break
    return samples


def write_outputs(stores: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = make_summary(stores)
    payload = {
        "generatedAt": CHECKED_AT,
        "brand": BRAND,
        "source": summary["source"],
        "stores": stores,
    }
    (OUT_DIR / "stores.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "audit-samples.json").write_text(json.dumps(make_audit_samples(stores), ensure_ascii=False, indent=2), encoding="utf-8")

    fields = [
        "brand",
        "storeName",
        "county",
        "district",
        "address",
        "phone",
        "hours",
        "officialSourceUrl",
        "gmbUrl",
        "gmbStatus",
        "takeoutAvailable",
        "deliveryAvailable",
        "takeoutProviders",
        "deliveryProviders",
        "otherProviders",
        "evidenceNotes",
        "checkedAt",
    ]
    with (OUT_DIR / "stores.csv").open("w", encoding="utf-8-sig", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        for store in stores:
            row = dict(store)
            for key in ("takeoutProviders", "deliveryProviders", "otherProviders"):
                row[key] = "、".join(row[key])
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> None:
    stores = parse_stores(fetch(OFFICIAL_STORE_LIST_URL))
    stores.sort(key=lambda item: (item["county"], item["district"], item["storeName"], item["address"]))
    apply_manual_verifications(stores)
    write_outputs(stores)
    print(f"Wrote {len(stores)} Milksha stores")


if __name__ == "__main__":
    main()
