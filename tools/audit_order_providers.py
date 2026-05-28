from __future__ import annotations

import argparse
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from fetch_official_stores import make_summary, write_outputs


DATA_PATH = Path("data/stores.json")
FOOTINDER_SEARCH_URL = "https://drink.footinder.com.tw/?s={query}"
CHECKED_AT = date.today().isoformat()


def fetch(url: str, timeout: int = 35) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def compact(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("臺", "台").replace("巿", "市")
    value = value.replace("❄️", "").replace("❄", "")
    value = re.sub(r"^\s*\d{3,6}\s*", "", value)
    value = re.sub(r"\s+", "", value)
    return value.lower()


def visible_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def candidate_queries(store: dict) -> list[str]:
    name = store["storeName"].replace("❄️", "").replace("❄", "").strip()
    address = re.sub(r"^\s*\d{3,6}\s*", "", store["address"]).strip()
    short_name = re.sub(r"^Milksha\s*Plus\s*", "", name, flags=re.I).strip()
    queries = [
        f"{name}",
        f"迷客夏Milksha {short_name}",
        f"{short_name} {address}",
    ]
    seen: set[str] = set()
    return [query for query in queries if query and not (query in seen or seen.add(query))]


def search_footinder(store: dict) -> str:
    best_href = ""
    target_name = compact(store["storeName"])
    target_address = compact(store["address"])
    phone_digits = re.sub(r"\D", "", store.get("phone", ""))

    for query in candidate_queries(store):
        page = fetch(FOOTINDER_SEARCH_URL.format(query=quote(query)))
        links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, flags=re.S)
        for href, label in links:
            href = html.unescape(href)
            label_text = compact(label)
            if "drink.footinder.com.tw" not in href:
                continue
            if "迷客夏" not in visible_text(label) and "milksha" not in label_text:
                continue
            if target_name and target_name in label_text:
                return href
            if best_href == "":
                best_href = href

        if best_href:
            detail = fetch(best_href)
            detail_compact = compact(detail)
            address_hit = target_address and target_address[:10] in detail_compact
            phone_hit = len(phone_digits) >= 7 and phone_digits[-7:] in re.sub(r"\D", "", detail)
            name_hit = target_name and target_name in detail_compact
            if address_hit or phone_hit or name_hit:
                return best_href
            best_href = ""
        time.sleep(0.25)
    return ""


def parse_delivery_providers(page: str) -> list[str]:
    providers: list[str] = []
    lower = page.lower()
    if "foodpanda.com.tw" in lower or "foodpanda" in lower:
        providers.append("foodpanda")
    if "ubereats.com" in lower or "uber eats" in lower:
        providers.append("Uber Eats")
    if "lin.ee" in lower:
        providers.append("lin.ee")
    return providers


def audit_store(store: dict) -> dict:
    try:
        evidence_url = search_footinder(store)
        if not evidence_url:
            store.update(
                {
                    "deliveryAvailable": None,
                    "deliveryProviders": [],
                    "orderAuditStatus": "needs_manual_review",
                    "providerEvidenceUrl": "",
                    "evidenceNotes": "未找到可比對的 Footinder 店家頁；需人工開啟 GMB 點餐按鈕確認外帶/外送服務商。",
                    "checkedAt": CHECKED_AT,
                }
            )
            return store

        detail = fetch(evidence_url)
        providers = parse_delivery_providers(detail)
        store["providerEvidenceUrl"] = evidence_url
        store["orderAuditStatus"] = "delivery_confirmed_by_footinder" if providers else "needs_manual_review"
        store["deliveryAvailable"] = bool(providers) if providers else None
        store["deliveryProviders"] = [provider for provider in providers if provider != "lin.ee"]
        if "lin.ee" in providers and "lin.ee" not in store["otherProviders"]:
            store["otherProviders"] = [*store["otherProviders"], "lin.ee"]
        store["takeoutAvailable"] = store.get("takeoutAvailable")
        store["takeoutProviders"] = store.get("takeoutProviders", [])
        store["evidenceNotes"] = (
            f"外送服務商依 Footinder 店家頁交叉比對：{', '.join(providers) if providers else '未列服務商'}。"
            "外帶服務商需人工開啟 Google 商家檔案點餐按鈕確認。"
        )
        store["checkedAt"] = CHECKED_AT
        return store
    except Exception as exc:
        store.update(
            {
                "orderAuditStatus": "unavailable_or_blocked",
                "providerEvidenceUrl": "",
                "evidenceNotes": f"批次查核失敗：{type(exc).__name__}。需人工開啟 GMB 點餐按鈕確認。",
                "checkedAt": CHECKED_AT,
            }
        )
        return store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    stores = payload["stores"]
    end = len(stores) if args.limit <= 0 else min(len(stores), args.offset + args.limit)
    indexes = list(range(args.offset, end))
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(audit_store, dict(stores[index])): index for index in indexes}
        for future in as_completed(futures):
            index = futures[future]
            stores[index] = future.result()
            print(f"{index + 1}/{len(stores)} {stores[index]['storeName']} {stores[index].get('orderAuditStatus')}")

    write_outputs(stores)
    summary = make_summary(stores)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
