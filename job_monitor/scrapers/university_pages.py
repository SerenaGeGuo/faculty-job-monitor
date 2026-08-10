from __future__ import annotations

from typing import List
from urllib.parse import urljoin

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

# Each entry is a department/school known for strong HCI, Information
# Science, or design/architecture research whose faculty-openings page
# is static, server-rendered HTML (confirmed reachable without a
# headless browser). "mode" selects how job links are recognized:
#
#   "peopleadmin" - links whose href contains "/postings/" are treated
#                   as individual job postings (PeopleAdmin/Interfolio
#                   style ATS).
#   "generic"     - any link whose visible text looks like a job
#                   posting title (see _looks_like_job_title below).
#
# Schools whose postings are fully JS-rendered (CMU/Workday, Stanford,
# UW Allen School/Interfolio SPA, RISD/Workday, ArtCenter/Cornerstone,
# UMich SI) are intentionally left out - they need a headless browser
# and should be checked manually for now.

UNIVERSITY_SOURCES = [
    {
        "name": "Georgia Tech College of Computing",
        "url": "https://www.cc.gatech.edu/faculty-position-opportunities",
        "mode": "table_rows",
    },
    {
        "name": "Georgia Tech School of Computer Science",
        "url": "https://scs.gatech.edu/faculty-hiring",
        "mode": "generic",
    },
    {
        "name": "MIT EECS",
        "url": "https://www.eecs.mit.edu/career-opportunities-at-eecs/",
        "mode": "generic",
    },
    {
        "name": "MIT Media Lab",
        "url": "https://www.media.mit.edu/about/job-opportunities/",
        "mode": "generic",
    },
    {
        "name": "UC Berkeley EECS",
        "url": "https://eecs.berkeley.edu/connect/faculty-jobs/",
        "mode": "generic",
    },
    {
        "name": "UC Irvine Donald Bren School of ICS",
        "url": "https://ics.uci.edu/academic-recruitment/",
        "mode": "generic",
    },
    {
        "name": "UC San Diego (AP Recruit, all divisions)",
        "url": "https://apol-recruit.ucsd.edu/apply/",
        "mode": "generic",
    },
    {
        "name": "CU Boulder ATLAS Institute",
        "url": "https://www.colorado.edu/atlas/jobs-atlas-institute",
        "mode": "generic",
    },
    {
        "name": "University of Maryland College of Information",
        "url": "https://info.umd.edu/about/jobs/",
        "mode": "generic",
    },
    # Cornell Bowers CIS (successor to Information Science)
    # careers page (bowers.cornell.edu/careers) renders an empty
    # body without JavaScript - skipped until a static page/API
    # is found.
    {
        "name": "Syracuse iSchool",
        "url": "https://www.sujobopps.com/postings/search?query=ischool",
        "mode": "peopleadmin",
    },
    {
        "name": "Indiana University Luddy School",
        "url": "https://indiana.peopleadmin.com/postings/search",
        "mode": "peopleadmin",
    },
    {
        "name": "Penn State College of IST",
        "url": "https://ist.psu.edu/faculty-openings",
        "mode": "generic",
    },
    {
        "name": "University of Toronto Faculty of Information",
        "url": "https://ischool.utoronto.ca/about-us/jobs/",
        "mode": "generic",
    },
    {
        "name": "TU Delft Industrial Design Engineering",
        "url": "https://careers.tudelft.nl/search/?q=industrial+design",
        "mode": "generic",
    },
    # IIT Institute of Design has no confirmed static jobs page -
    # its careers portal did not surface a working PeopleAdmin/ATS
    # URL during setup. Check id.iit.edu and iit.edu/hr/careers
    # manually until a scrapable endpoint is identified.
    {
        "name": "University of Washington iSchool",
        "url": "https://ischool.uw.edu/about/jobs/faculty",
        "mode": "generic",
    },
]

JOB_TITLE_KEYWORDS = [
    "professor",
    "faculty",
    "tenure",
    "lecturer",
    "instructor",
    "chair",
    "scientist",
    "fellow",
    "open rank",
]

NAV_BLOCKLIST = {
    "home",
    "about",
    "contact",
    "search",
    "login",
    "log in",
    "apply now",
    "apply",
    "submit",
    "read more",
    "learn more",
    "more information",
    "back to top",
    "skip to main content",
    "faculty positions",
    "faculty position opportunities",
    "faculty openings",
    "faculty hiring",
    "faculty jobs",
    "current openings",
    "open positions",
    "view all",
    "see all",
    "next",
    "previous",
}


def _looks_like_job_title(text: str) -> bool:

    cleaned = text.strip()
    lowered = cleaned.lower()

    if len(cleaned) < 12:
        return False

    if lowered in NAV_BLOCKLIST:
        return False

    return any(
        keyword in lowered for keyword in JOB_TITLE_KEYWORDS
    )


def _link_title(link) -> str:
    """
    Prefer an accessibility aria-label over the visible link text.
    Some ATS pages (e.g. UC San Diego's AP Recruit) render only a
    posting code ("JPF04488") as visible text and put the actual
    job title in aria-label, e.g. "More information about
    JPF04488: Lecturer in History".
    """

    aria_label = link.get("aria-label", "")

    if ":" in aria_label:
        return aria_label.split(":", 1)[1].strip()

    return link.get_text(" ", strip=True)


def _extract_generic_jobs(
    soup: BeautifulSoup,
    base_url: str,
    source_name: str,
) -> List[Job]:

    jobs: List[Job] = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):

        href = link["href"].strip()

        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        title = _link_title(link)

        if not _looks_like_job_title(title):
            continue

        url = urljoin(base_url, href)

        if url in seen_urls:
            continue

        seen_urls.add(url)

        jobs.append(
            Job(
                title=title,
                organization=source_name,
                url=url,
                subject_areas="",
                description="",
                position_type="",
                deadline="",
                source=f"University: {source_name}",
            )
        )

    return jobs


def _extract_peopleadmin_jobs(
    soup: BeautifulSoup,
    base_url: str,
    source_name: str,
) -> List[Job]:

    jobs: List[Job] = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):

        href = link["href"].strip()

        if "/postings/" not in href:
            continue

        title = link.get_text(" ", strip=True)

        if not title or len(title) < 8:
            continue

        if title.lower() in NAV_BLOCKLIST:
            continue

        url = urljoin(base_url, href)

        if url in seen_urls:
            continue

        seen_urls.add(url)

        jobs.append(
            Job(
                title=title,
                organization=source_name,
                url=url,
                subject_areas="",
                description="",
                position_type="",
                deadline="",
                source=f"University: {source_name}",
            )
        )

    return jobs


def _extract_table_row_jobs(
    soup: BeautifulSoup,
    base_url: str,
    source_name: str,
) -> List[Job]:
    """
    Some department pages (e.g. Georgia Tech CoC) list open
    positions as plain-text table rows with no per-row link at
    all. There is no individual posting URL to give in that case,
    so every match points back at the listing page itself.
    """

    jobs: List[Job] = []
    seen_titles = set()

    for row in soup.find_all("tr"):

        cell = row.find("td")

        if not cell:
            continue

        title = cell.get_text(" ", strip=True)

        if not _looks_like_job_title(title):
            continue

        if title in seen_titles:
            continue

        seen_titles.add(title)

        jobs.append(
            Job(
                title=title,
                organization=source_name,
                url=base_url,
                subject_areas="",
                description="",
                position_type="",
                deadline="",
                source=f"University: {source_name}",
            )
        )

    return jobs


def fetch_source_jobs(
    source: dict,
    timeout: int = 30,
) -> List[Job]:
    """
    Fetch job listings from a single configured university source.
    """

    response = requests.get(
        source["url"],
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    if source["mode"] == "peopleadmin":
        return _extract_peopleadmin_jobs(
            soup, source["url"], source["name"]
        )

    if source["mode"] == "table_rows":
        return _extract_table_row_jobs(
            soup, source["url"], source["name"]
        )

    return _extract_generic_jobs(
        soup, source["url"], source["name"]
    )


def fetch_jobs(timeout: int = 30) -> List[Job]:
    """
    Fetch job listings from every configured university-specific
    faculty-openings page. Each source is isolated so a single
    failing/blocked school does not stop the others.
    """

    jobs: List[Job] = []

    for source in UNIVERSITY_SOURCES:

        print(f"  Reading {source['name']}...")

        try:
            source_jobs = fetch_source_jobs(
                source, timeout=timeout
            )

        except requests.RequestException as error:
            print(f"    Could not read {source['name']}: {error}")
            continue

        print(f"    Found {len(source_jobs)} candidate links")

        jobs.extend(source_jobs)

    return jobs
