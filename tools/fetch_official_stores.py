from __future__ import annotations

import csv
import html
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


BASE_URL = "https://www.chage.com.tw/"
START_URL = "https://www.chage.com.tw/edcontent.php?cid=102&lang=tw&tb=3"
OUT_DIR = Path("data")


def fetch(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            )
        },
    )
    with urlopen(req, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_field(text: str, label: str) -> str:
    for line in text.splitlines():
        if label not in line:
            continue
        value = re.sub(rf"^.*?{label}\s*[:：]\s*", "", line).strip()
        return re.sub(r"\s+", " ", value)
    return ""


def get_city_links() -> list[dict[str, str]]:
    page = fetch(START_URL)
    matches = re.findall(
        r'<a href="(?P<href>https://www\.chage\.com\.tw/edcontent\.php\?lang=tw(?:&amp;|&)tb=3(?:&amp;|&)cid=(?P<cid>\d+))"[^>]*title="(?P<title>[^"]+門市)"',
        page,
    )
    seen: set[str] = set()
    links: list[dict[str, str]] = []
    for href, cid, title in matches:
        if cid in seen:
            continue
        seen.add(cid)
        links.append(
            {
                "city_group": html.unescape(title),
                "cid": cid,
                "url": html.unescape(href),
            }
        )
    return links


def page_urls_for_city(city: dict[str, str]) -> list[str]:
    first = fetch(city["url"])
    pages = {1}
    for page in re.findall(r"currentpage=(\d+)", first):
        pages.add(int(page))
    urls = []
    for page in sorted(pages):
        suffix = "" if page == 1 else f"&currentpage={page}"
        urls.append(f'{city["url"]}{suffix}')
    return urls


def parse_store_items(page: str, city: dict[str, str], source_url: str) -> list[dict[str, str]]:
    chunks = re.split(r'<div class="row item">', page)[1:]
    stores: list[dict[str, str]] = []
    for chunk in chunks:
        title_match = re.search(
            r'edcontent_d\.php\?lang=tw(?:&amp;|&)tb=3(?:&amp;|&)id=(?P<id>\d+)"\s+[^>]*title="(?P<title>[^"]+)"',
            chunk,
        )
        if not title_match:
            continue
        store_id = title_match.group("id")
        name = html.unescape(title_match.group("title")).strip()
        detail_url = urljoin(BASE_URL, f"edcontent_d.php?lang=tw&tb=3&id={store_id}")

        summary = strip_tags(chunk)

        address = normalize_field(summary, "門市地址")
        phone = normalize_field(summary, "門市電話")
        hours = normalize_field(summary, "營業時間")
        query = f"茶聚CHAGE{name} {address}".strip()
        maps_url = f"https://www.google.com/maps/search/?api=1&query={quote(query)}"

        stores.append(
            {
                "official_id": store_id,
                "official_name": name,
                "city_group": city["city_group"],
                "address": address,
                "phone": phone,
                "hours": hours,
                "official_url": detail_url,
                "source_list_url": source_url,
                "gmb_name": "",
                "gmb_url": maps_url,
                "gmb_status": "待查核",
                "has_takeout_order": None,
                "has_delivery_order": None,
                "takeout_providers": [],
                "delivery_providers": [],
                "other_providers": [],
                "verification_note": "已建立 Google Maps 查詢連結；尚未逐店確認 GMB 點餐彈窗。",
                "verified_at": "",
            }
        )
    return stores


def apply_manual_verifications(stores: list[dict]) -> None:
    for store in stores:
        if "永康中華" not in store["official_name"]:
            continue
        store.update(
            {
                "gmb_name": "茶聚CHAGE永康中華店",
                "gmb_status": "已人工確認",
                "has_takeout_order": True,
                "has_delivery_order": True,
                "takeout_providers": ["foodpanda", "lin.ee"],
                "delivery_providers": ["foodpanda", "lin.ee", "Uber Eats"],
                "other_providers": ["lin.ee"],
                "verification_note": "依使用者提供的 Google 商家檔案截圖人工標註：外帶含 foodpanda、lin.ee；外送含 foodpanda、lin.ee、Uber Eats。",
                "verified_at": date.today().isoformat(),
            }
        )


def write_outputs(stores: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": date.today().isoformat(),
        "source": {
            "official_store_list": START_URL,
            "notes": "GMB statuses marked 待查核 were not counted as confirmed order-service usage.",
        },
        "stores": stores,
    }
    (OUT_DIR / "stores.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = [
        "official_id",
        "official_name",
        "city_group",
        "address",
        "phone",
        "hours",
        "official_url",
        "gmb_name",
        "gmb_url",
        "gmb_status",
        "has_takeout_order",
        "has_delivery_order",
        "takeout_providers",
        "delivery_providers",
        "other_providers",
        "verification_note",
        "verified_at",
    ]
    with (OUT_DIR / "stores.csv").open("w", encoding="utf-8-sig", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        for store in stores:
            row = dict(store)
            for key in ("takeout_providers", "delivery_providers", "other_providers"):
                row[key] = "、".join(row[key])
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> None:
    city_links = get_city_links()
    all_stores: list[dict] = []
    seen_ids: set[str] = set()
    for city in city_links:
        for url in page_urls_for_city(city):
            page = fetch(url)
            for store in parse_store_items(page, city, url):
                if store["official_id"] in seen_ids:
                    continue
                seen_ids.add(store["official_id"])
                all_stores.append(store)
            time.sleep(0.2)

    all_stores.sort(key=lambda item: (item["city_group"], item["official_name"], item["official_id"]))
    apply_manual_verifications(all_stores)
    write_outputs(all_stores)
    print(f"Wrote {len(all_stores)} stores to {OUT_DIR / 'stores.json'}")


if __name__ == "__main__":
    main()
