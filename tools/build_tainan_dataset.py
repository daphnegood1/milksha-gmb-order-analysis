from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_SOURCE = Path("data/source-stores.csv")
FALLBACK_SOURCE = Path("data/stores.csv")
STORES_JSON = Path("data/stores.json")
STORES_CSV = Path("data/stores.csv")
SUMMARY_JSON = Path("data/summary.json")
OFFICIAL_STORE_URL = "https://www.milksha.com/store_detail.php?uID=1"

DISTRICT_RE = re.compile(r"(?:臺南市|台南市|台南巿)\s*([^路街大道巷弄段號,，\s]{1,8}區)")
NIDIN_ID_RE = re.compile(r"門市 ID\s*(\d+)")


def normalize_bool(value: str) -> bool | None:
    normalized = (value or "").strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def split_providers(value: str) -> list[str]:
    providers: list[str] = []
    for item in re.split(r"[、,]", value or ""):
        provider = item.strip()
        if provider and provider not in providers:
            providers.append(provider)
    return providers


def is_tainan(row: dict[str, str]) -> bool:
    text = " ".join([row.get("storeName", ""), row.get("county", ""), row.get("address", "")])
    return any(keyword in text for keyword in ("臺南", "台南", "台南巿"))


def district_from(row: dict[str, str]) -> str:
    if (row.get("district") or "").strip():
        district = row["district"].strip()
        return f"{district}區" if district == "新市" else district
    match = DISTRICT_RE.search(row.get("address", ""))
    return match.group(1) if match else ""


def evidence_note(row: dict[str, str]) -> str:
    return re.sub(r"\s+", " ", row.get("evidenceNotes", "")).strip()


def nidin_url_from(note: str) -> str:
    match = NIDIN_ID_RE.search(note)
    return f"https://milksha.nidin.shop/menu/{match.group(1)}" if match else ""


def build_provider_evidence(row: dict[str, str], providers: list[str]) -> list[dict[str, str]]:
    note = evidence_note(row)
    evidence: list[dict[str, str]] = []
    if "Nidin" in providers:
        evidence.append(
            {
                "provider": "Nidin",
                "service": "takeout_delivery",
                "source": "迷客夏官方 Nidin 點餐 API",
                "url": nidin_url_from(note),
                "status": "confirmed_public_source",
            }
        )
    for provider in ("foodpanda", "Uber Eats"):
        if provider in providers:
            evidence.append(
                {
                    "provider": provider,
                    "service": "delivery",
                    "source": "Footinder 店家頁交叉比對",
                    "url": "",
                    "status": "confirmed_external_index",
                }
            )
    if "lin.ee" in providers:
        evidence.append(
            {
                "provider": "lin.ee",
                "service": "other",
                "source": "GMB 或外部連結紀錄",
                "url": "",
                "status": "needs_manual_review",
            }
        )
    return evidence


def google_text_search(store: dict, api_key: str) -> dict:
    body = json.dumps(
        {
            "textQuery": f"迷客夏 {store['storeName']} {store['address']}",
            "languageCode": "zh-TW",
            "regionCode": "TW",
        }
    ).encode("utf-8")
    request = Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.googleMapsUri,places.businessStatus,"
                "places.takeout,places.delivery,places.regularOpeningHours"
            ),
        },
        method="POST",
    )
    with urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    places = payload.get("places") or []
    return places[0] if places else {}


def apply_google_places(stores: list[dict], api_key: str) -> None:
    if not api_key:
        return
    for store in stores:
        try:
            place = google_text_search(store, api_key)
        except Exception as exc:
            store["googlePlaces"] = {
                "status": "error",
                "error": type(exc).__name__,
                "checkedAt": date.today().isoformat(),
            }
            continue
        if not place:
            store["googlePlaces"] = {"status": "not_found", "checkedAt": date.today().isoformat()}
            continue
        store["googlePlaces"] = {
            "status": "matched",
            "placeId": place.get("id", ""),
            "businessStatus": place.get("businessStatus", ""),
            "takeout": place.get("takeout"),
            "delivery": place.get("delivery"),
            "checkedAt": date.today().isoformat(),
        }
        if place.get("googleMapsUri"):
            store["gmbUrl"] = place["googleMapsUri"]
        if isinstance(place.get("takeout"), bool):
            store["takeoutAvailable"] = place["takeout"]
            store["gmbEvidence"]["takeout"] = "Google Places API"
        if isinstance(place.get("delivery"), bool):
            store["deliveryAvailable"] = place["delivery"]
            store["gmbEvidence"]["delivery"] = "Google Places API"
        if isinstance(place.get("takeout"), bool) or isinstance(place.get("delivery"), bool):
            store["confidence"] = "high"


def make_store(row: dict[str, str]) -> dict:
    takeout_providers = split_providers(row.get("takeoutProviders", ""))
    delivery_providers = split_providers(row.get("deliveryProviders", ""))
    other_providers = split_providers(row.get("otherProviders", ""))
    provider_names = sorted(set(takeout_providers + delivery_providers + other_providers))
    note = evidence_note(row)
    takeout_available = normalize_bool(row.get("takeoutAvailable", ""))
    delivery_available = normalize_bool(row.get("deliveryAvailable", ""))
    needs_review = takeout_available is None or delivery_available is None

    return {
        "brand": "迷客夏",
        "storeName": row.get("storeName", "").strip(),
        "county": "臺南市",
        "district": district_from(row),
        "address": row.get("address", "").replace("台南巿", "臺南市").strip(),
        "phone": row.get("phone", "").strip(),
        "hours": row.get("hours", "").strip(),
        "officialSourceUrl": row.get("officialSourceUrl", OFFICIAL_STORE_URL).strip() or OFFICIAL_STORE_URL,
        "gmbUrl": row.get("gmbUrl", "").strip(),
        "gmbStatus": row.get("gmbStatus", "confirmed").strip() or "confirmed",
        "takeoutAvailable": takeout_available,
        "deliveryAvailable": delivery_available,
        "takeoutProviders": takeout_providers,
        "deliveryProviders": delivery_providers,
        "otherProviders": other_providers,
        "providerNames": provider_names,
        "gmbEvidence": {
            "takeout": "待 Google Places API 或人工開啟 GMB 點餐按鈕確認",
            "delivery": "待 Google Places API 或人工開啟 GMB 點餐按鈕確認",
            "url": row.get("gmbUrl", "").strip(),
        },
        "nidinEvidence": {
            "matched": "Nidin" in provider_names,
            "url": nidin_url_from(note),
            "source": "迷客夏官方 Nidin 點餐 API" if "Nidin" in provider_names else "",
        },
        "deliveryPlatformEvidence": build_provider_evidence(row, provider_names),
        "manualReviewStatus": "needs_review" if needs_review else "public_sources_verified",
        "verificationNote": (
            "尚無外帶/外送服務判斷，需人工開啟 GMB 或補 API 查核。"
            if needs_review
            else "外帶/外送狀態來自公開資料交叉比對；GMB 點餐按鈕供應商仍需 API 或人工複核。"
        ),
        "evidenceNotes": note,
        "confidence": "low" if needs_review else "medium",
        "checkedAt": row.get("checkedAt", "").strip() or date.today().isoformat(),
    }


def make_summary(stores: list[dict]) -> dict:
    provider_counts = Counter(provider for store in stores for provider in set(store["providerNames"]))
    takeout_counts = Counter(provider for store in stores for provider in set(store["takeoutProviders"]))
    delivery_counts = Counter(provider for store in stores for provider in set(store["deliveryProviders"]))
    return {
        "generatedAt": date.today().isoformat(),
        "sourceCheckedAt": max((store["checkedAt"] for store in stores), default=""),
        "scope": "臺南市迷客夏",
        "storeCount": len(stores),
        "gmbFoundCount": sum(1 for store in stores if store["gmbStatus"] == "confirmed" and store["gmbUrl"]),
        "takeoutCount": sum(1 for store in stores if store["takeoutAvailable"] is True),
        "deliveryCount": sum(1 for store in stores if store["deliveryAvailable"] is True),
        "unknownCount": sum(
            1 for store in stores if store["takeoutAvailable"] is None or store["deliveryAvailable"] is None
        ),
        "providerCounts": dict(sorted(provider_counts.items())),
        "takeoutProviderCounts": dict(sorted(takeout_counts.items())),
        "deliveryProviderCounts": dict(sorted(delivery_counts.items())),
        "sources": {
            "officialStoreList": OFFICIAL_STORE_URL,
            "googlePlacesApi": "enabled by GOOGLE_MAPS_API_KEY" if os.getenv("GOOGLE_MAPS_API_KEY") else "not configured",
            "fallback": "data/source-stores.csv",
        },
    }


def write_csv(stores: list[dict]) -> None:
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
        "providerNames",
        "manualReviewStatus",
        "confidence",
        "verificationNote",
        "checkedAt",
    ]
    with STORES_CSV.open("w", encoding="utf-8-sig", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        for store in stores:
            row = dict(store)
            for key in ("takeoutProviders", "deliveryProviders", "otherProviders", "providerNames"):
                row[key] = "、".join(row[key])
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE if DEFAULT_SOURCE.exists() else FALLBACK_SOURCE)
    parser.add_argument("--skip-google", action="store_true")
    args = parser.parse_args()

    rows = list(csv.DictReader(args.source.open("r", encoding="utf-8-sig", newline="")))
    stores = [make_store(row) for row in rows if is_tainan(row)]
    stores.sort(key=lambda store: (store["district"], store["storeName"], store["address"]))

    api_key = "" if args.skip_google else os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    apply_google_places(stores, api_key)

    summary = make_summary(stores)
    payload = {
        "generatedAt": summary["generatedAt"],
        "scope": summary["scope"],
        "brand": "迷客夏",
        "summary": summary,
        "stores": stores,
    }
    STORES_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(stores)
    print(f"Wrote {len(stores)} Tainan Milksha stores")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
