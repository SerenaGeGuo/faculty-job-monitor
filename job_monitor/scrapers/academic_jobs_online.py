from __future__ import annotations

from dataclasses import dataclass
from typing import List
from urllib.parse import urljoin
import re

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://academicjobsonline.org"
LIST_URL = "https://academicjobsonline.org/ajo/jobs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
}


@dataclass
class Job:
    title: str
    organization: str
    url: str
    subject_areas: str = ""
    description: str = ""
    position_type: str = ""
    deadline: str = ""
    source: str = "AcademicJobsOnline"


def fetch_jobs(timeout: int = 30, max_pages: int = 30) -> List[Job]:
    """
    Fetch job listings from all available AcademicJobsOnline pages.
    """

    jobs: List[Job] = []
    seen_urls = set()

    next_url = LIST_URL
    page_count = 0

    while next_url and page_count < max_pages:

        response = requests.get(
            next_url,
            headers=HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        current_organization = ""

        for element in soup.find_all(["h3", "a"]):

            # Organization heading
            if element.name == "h3":
                current_organization = element.get_text(
                    " ", strip=True
                )
                continue

            href = element.get("href", "")

            # Keep only individual job links
            if "/ajo/jobs/" not in href:
                continue

            job_id = href.rstrip("/").split("/")[-1]

            if not job_id.isdigit():
                continue

            url = urljoin(BASE_URL, href)

            if url in seen_urls:
                continue

            job_code = element.get_text(" ", strip=True)

            parent = element.find_parent("li")

            if parent is not None:
                full_text = parent.get_text(
                    " ", strip=True
                )

                title = re.sub(
                    rf"^\[\s*{re.escape(job_code)}\s*\]\s*",
                    "",
                    full_text,
                ).strip()

                title = re.sub(
                    r"\s+Apply$",
                    "",
                    title,
                ).strip()

            else:
                title = job_code

            if not title:
                continue

            seen_urls.add(url)

            jobs.append(
                Job(
                    title=title,
                    organization=current_organization,
                    url=url,
                )
            )

        # Look for the "next..." pagination link
        next_link = None

        for link in soup.find_all("a"):
            link_text = link.get_text(
                " ", strip=True
            ).lower()

            if link_text.startswith("next"):
                next_link = link
                break

        if next_link and next_link.get("href"):
            next_url = urljoin(
                BASE_URL,
                next_link["href"],
            )
        else:
            next_url = None

        page_count += 1

    return jobs

def _extract_field(lines, start_label, stop_labels):
    """
    Extract text appearing after a label and before the next known label.
    """

    try:
        start_index = lines.index(start_label)
    except ValueError:
        return ""

    collected = []

    for line in lines[start_index + 1:]:
        if line in stop_labels:
            break

        collected.append(line)

    return " ".join(collected).strip()


def fetch_job_details(job: Job, timeout: int = 30) -> Job:
    """
    Open an individual AcademicJobsOnline posting and extract
    detailed metadata.
    """

    response = requests.get(
        job.url,
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    lines = [
        text.strip()
        for text in soup.stripped_strings
        if text.strip()
    ]

    labels = {
        "Position ID:",
        "Position Title:",
        "Position Type:",
        "Position Location:",
        "Subject Areas:",
        "Appl Deadline:",
        "Position Description:",
        "Application Materials Required:",
        "Further Info:",
    }

    job.position_type = _extract_field(
        lines,
        "Position Type:",
        labels,
    )

    job.subject_areas = _extract_field(
        lines,
        "Subject Areas:",
        labels,
    )

    job.deadline = _extract_field(
        lines,
        "Appl Deadline:",
        labels,
    )

    job.description = _extract_field(
        lines,
        "Position Description:",
        {
            "Application Materials Required:",
            "Further Info:",
        },
    )

    return job