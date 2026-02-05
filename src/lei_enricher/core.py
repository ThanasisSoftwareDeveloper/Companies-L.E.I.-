from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LEI_REGEX = re.compile(r"^[0-9A-Z]{20}$")


@dataclass
class LeiResult:
    entity_status: Optional[str] = None
    next_renewal_date: Optional[str] = None
    source: Optional[str] = None


def normalize_lei(value: object) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().upper()
    s = re.sub(r"\s+", "", s)
    return s or None


def is_valid_lei(lei: str) -> bool:
    return bool(LEI_REGEX.match(lei))


def chunked(items: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20))
    s.headers.update(
        {
            "User-Agent": "LEI-Enricher/0.1 (contact: it-ops@yourbank.example)",
            "Accept": "application/json,text/html",
        }
    )
    return s


def parse_gleif_item(item: dict) -> Tuple[str, LeiResult]:
    attrs = item.get("attributes", {}) or {}
    lei = attrs.get("lei") or item.get("id") or ""
    entity = attrs.get("entity", {}) or {}
    registration = attrs.get("registration", {}) or {}

    status = entity.get("status")
    renewal = registration.get("nextRenewalDate")

    if isinstance(status, str):
        status = status.strip().upper()
    if isinstance(renewal, str):
        renewal = renewal.strip()

    return lei, LeiResult(entity_status=status, next_renewal_date=renewal, source="gleif")


class GleifClient:
    """
    Prefer API calls, not scraping search.gleif.org.
    Uses batching: filter[lei]=LEI1,LEI2,... (up to 200)
    """

    def __init__(self, session: Optional[requests.Session] = None, throttle_s: float = 0.2) -> None:
        self.session = session or make_session()
        self.throttle_s = throttle_s

    def lookup_batch(self, leis: List[str]) -> Dict[str, LeiResult]:
        if not leis:
            return {}
        lei_csv = ",".join(leis)
        url = f"https://api.gleif.org/api/v1/lei-records?page[size]={len(leis)}&filter[lei]={lei_csv}"

        if self.throttle_s > 0:
            time.sleep(self.throttle_s)

        r = self.session.get(url, timeout=30)
        if r.status_code != 200:
            return {}

        payload = r.json()
        out: Dict[str, LeiResult] = {}
        for item in payload.get("data", []) or []:
            lei, res = parse_gleif_item(item)
            if lei:
                out[lei] = res
        return out


class LeiLookupFallback:
    """
    HTML parse fallback for misses only. Throttle heavily.
    """

    def __init__(self, session: Optional[requests.Session] = None, throttle_s: float = 1.0) -> None:
        self.session = session or make_session()
        self.throttle_s = throttle_s

    def lookup(self, lei: str) -> LeiResult:
        url = f"https://www.lei-lookup.com/record/{lei}/"
        if self.throttle_s > 0:
            time.sleep(self.throttle_s)

        r = self.session.get(url, timeout=30)
        if r.status_code != 200 or not r.text:
            return LeiResult(source="lei-lookup")

        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text("\n", strip=True)

        status = None
        renewal = None

        m1 = re.search(r"Entity status\.?\s*([A-Z]+)", text, flags=re.IGNORECASE)
        if m1:
            status = m1.group(1).strip().upper()

        m2 = re.search(r"Next renewal date[,\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, flags=re.IGNORECASE)
        if m2:
            renewal = m2.group(1).strip()

        return LeiResult(entity_status=status, next_renewal_date=renewal, source="lei-lookup")