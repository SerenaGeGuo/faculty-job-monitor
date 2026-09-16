from __future__ import annotations

import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

DEAD_STATUS_CODES = {404, 410}

DEAD_PAGE_PHRASES = [
    "position has been filled",
    "position has been closed",
    "posting has been removed",
    "no longer accepting applications",
    "this search has been closed",
    "this position is no longer available",
    "job has expired",
    "recruitment has been closed",
]

MONTH_NAMES = (
    r"January|February|March|April|May|June|July|August|"
    r"September|October|November|December"
)

DATE_PATTERNS = [
    re.compile(rf"(?:{MONTH_NAMES})\s+\d{{1,2}},?\s+20\d{{2}}", re.IGNORECASE),
    re.compile(r"\d{1,2}/\d{1,2}/20\d{2}"),
    re.compile(r"20\d{2}-\d{2}-\d{2}"),
    re.compile(r"20\d{2}/\d{2}/\d{2}"),
]

DEADLINE_KEYWORDS = [
    "application deadline",
    "deadline for applications",
    "deadline to apply",
    "review of applications will begin",
    "applications will be reviewed beginning",
    "screening of applications will begin",
    "priority will be given to applications received by",
    "applications received by",
    "for full consideration, apply by",
    "apply by",
    "close date",
    "closing date",
    "deadline",
]


def _extract_deadline_from_text(text: str) -> str:
    """
    Best-effort extraction of a deadline date from an individual
    posting's page text, used only as a fallback when the original
    scrape never captured a structured deadline. Not guaranteed to
    be correct - phrasing and date formats vary a lot across ATS
    platforms.
    """

    if not text:
        return ""

    lower = text.lower()

    if "open until filled" in lower or "until filled" in lower:
        return "open until filled"

    for keyword in DEADLINE_KEYWORDS:

        idx = lower.find(keyword)

        if idx == -1:
            continue

        window = text[idx: idx + 200]

        for pattern in DATE_PATTERNS:
            match = pattern.search(window)
            if match:
                return match.group(0)

    return ""


def check_link(
    url: str,
    existing_deadline: str = "",
    timeout: int = 15,
) -> dict:
    """
    Fetch a single posting URL and report whether it's still live,
    plus a best-effort deadline extracted from the page if the
    caller didn't already have one.

    Returns a dict with:
        status: "Live" | "Expired" | "Unknown"
        deadline: existing_deadline if non-empty, else whatever this
                  function could find on the page, else ""
    """

    result = {
        "status": "Unknown",
        "deadline": existing_deadline.strip() if existing_deadline else "",
    }

    if not url:
        return result

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )

    except requests.RequestException:
        return result

    if response.status_code in DEAD_STATUS_CODES:
        result["status"] = "Expired"
        return result

    if response.status_code != 200:
        return result

    page_text = BeautifulSoup(
        response.text, "lxml"
    ).get_text(" ", strip=True)

    lower_text = page_text.lower()

    if any(phrase in lower_text for phrase in DEAD_PAGE_PHRASES):
        result["status"] = "Expired"
        return result

    result["status"] = "Live"

    if not result["deadline"]:
        result["deadline"] = _extract_deadline_from_text(page_text)

    return result


def check_links(
    rows: list,
    timeout: int = 15,
    delay: float = 0.2,
    progress_callback: Optional[callable] = None,
) -> list:
    """
    Run check_link() over every row (each a dict with at least "url"
    and "deadline" keys) and return new dicts with "link_status" and
    a possibly-filled-in "deadline" merged in. Does not mutate the
    input rows or touch the database - this is purely for building
    an accurate export.
    """

    enriched = []

    for index, row in enumerate(rows, start=1):

        check_result = check_link(
            row.get("url", ""),
            existing_deadline=row.get("deadline", "") or "",
            timeout=timeout,
        )

        merged = dict(row)
        merged["link_status"] = check_result["status"]
        merged["deadline"] = check_result["deadline"]

        enriched.append(merged)

        if progress_callback:
            progress_callback(index, len(rows), merged)

        time.sleep(delay)

    return enriched
