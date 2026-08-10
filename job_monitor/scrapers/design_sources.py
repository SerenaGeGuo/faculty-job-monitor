from __future__ import annotations

from typing import List

import requests
from bs4 import BeautifulSoup

from job_monitor.scrapers.academic_jobs_online import Job

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

# NOTE: SIGCHI's own jobs page (sigchi.org) no longer exists, and its
# CHI-JOBS mailing-list archive is behind a Cloudflare wall that blocks
# automated access. AIGA's main Design Jobs board is also Cloudflare/
# login-gated. We use AIGA's Design Educators Community board instead,
# which is open and carries faculty postings.

ACSA_URL = "https://www.acsa-arch.org/opportunities/find-a-job/"
AIGA_EDUCATORS_URL = "https://educators.aiga.org/jobs/"


def fetch_acsa_jobs(timeout: int = 30) -> List[Job]:
    """
    Fetch faculty job listings from the Association of Collegiate
    Schools of Architecture (ACSA) job board.
    """

    response = requests.get(
        ACSA_URL,
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    jobs: List[Job] = []
    seen_urls = set()

    for entry in soup.select("div.post-type-job_listing"):

        title_link = entry.select_one("h4.entry-title a")

        if not title_link:
            continue

        title = title_link.get_text(" ", strip=True)
        url = title_link.get("href", "").strip()

        if not title or not url or url in seen_urls:
            continue

        organization = ""

        org_paragraph = entry.select_one(".entry-content-inner p")

        if org_paragraph:
            organization = org_paragraph.get_text(
                " ", strip=True
            )

        posted = ""

        date_div = entry.select_one(".entry-date")

        if date_div:
            posted = date_div.get_text(
                " ", strip=True
            )

        seen_urls.add(url)

        jobs.append(
            Job(
                title=title,
                organization=organization,
                url=url,
                subject_areas="",
                description=f"Posted: {posted}" if posted else "",
                position_type="",
                deadline="",
                source="ACSA",
            )
        )

    return jobs


def fetch_aiga_educators_jobs(timeout: int = 30) -> List[Job]:
    """
    Fetch faculty design job listings from the AIGA Design
    Educators Community job board.
    """

    response = requests.get(
        AIGA_EDUCATORS_URL,
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    jobs: List[Job] = []
    seen_urls = set()

    for entry in soup.select("a.link-block"):

        title_div = entry.select_one(".job-item-title")

        if not title_div:
            continue

        title = title_div.get_text(" ", strip=True)
        url = entry.get("href", "").strip()

        if not title or not url or url in seen_urls:
            continue

        organization = ""

        org_div = entry.select_one(".job-item-company-name")

        if org_div:
            organization = org_div.get_text(
                " ", strip=True
            )

        location = ""

        location_span = entry.select_one(".job-item-location")

        if location_span:
            location = location_span.get_text(
                " ", strip=True
            )

        seen_urls.add(url)

        jobs.append(
            Job(
                title=title,
                organization=organization,
                url=url,
                subject_areas="",
                description=f"Location: {location}" if location else "",
                position_type="",
                deadline="",
                source="AIGA Educators",
            )
        )

    return jobs


def fetch_jobs(timeout: int = 30) -> List[Job]:
    """
    Fetch faculty job listings from all available design and
    architecture job boards.
    """

    jobs: List[Job] = []

    try:
        jobs.extend(fetch_acsa_jobs(timeout=timeout))
    except requests.RequestException as error:
        print(f"  Could not read ACSA: {error}")

    try:
        jobs.extend(fetch_aiga_educators_jobs(timeout=timeout))
    except requests.RequestException as error:
        print(f"  Could not read AIGA Educators: {error}")

    return jobs
