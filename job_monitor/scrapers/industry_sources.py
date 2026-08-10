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
    ),
    "Accept": "application/json",
}

# NOTE: Google Research, Microsoft Research, Meta (FAIR/Reality Labs),
# IBM Research, and Boston Dynamics AI Institute do not expose a public,
# unauthenticated JSON job feed (fully JS-rendered career sites or
# session-gated APIs) and are not included here. They should be checked
# manually until a scrapable feed becomes available.

GREENHOUSE_BOARDS = {
    "DeepMind": "deepmind",
    "Waymo": "waymo",
}

LEVER_BOARDS = {
    "Toyota Research Institute": "tri",
}

SMARTRECRUITERS_COMPANIES = {
    "Bosch": "BoschGroup",
}

WORKDAY_BOARDS = {
    "Adobe": {
        "tenant": "adobe",
        "host": "adobe.wd5.myworkdayjobs.com",
        "site": "external_experienced",
    },
    "Autodesk": {
        "tenant": "autodesk",
        "host": "autodesk.wd1.myworkdayjobs.com",
        "site": "Ext",
    },
    "NVIDIA": {
        "tenant": "nvidia",
        "host": "nvidia.wd5.myworkdayjobs.com",
        "site": "NVIDIAExternalCareerSite",
    },
}


def _strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""

    return BeautifulSoup(raw_html, "lxml").get_text(
        " ", strip=True
    )


def fetch_greenhouse_jobs(
    company_name: str,
    board_token: str,
    timeout: int = 30,
) -> List[Job]:
    """
    Fetch job listings from a company's Greenhouse job board API.
    """

    url = (
        f"https://boards-api.greenhouse.io/v1/boards/"
        f"{board_token}/jobs?content=true"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()

    jobs: List[Job] = []

    for item in data.get("jobs", []):

        title = item.get("title", "").strip()
        url_ = item.get("absolute_url", "").strip()

        if not title or not url_:
            continue

        location = (item.get("location") or {}).get(
            "name", ""
        )

        description = _strip_html(item.get("content", ""))

        jobs.append(
            Job(
                title=title,
                organization=company_name,
                url=url_,
                subject_areas="",
                description=(
                    f"Location: {location}\n{description}"
                    if location
                    else description
                ),
                position_type="",
                deadline="",
                source=f"Industry: {company_name}",
            )
        )

    return jobs


def fetch_lever_jobs(
    company_name: str,
    slug: str,
    timeout: int = 30,
) -> List[Job]:
    """
    Fetch job listings from a company's Lever job board API.
    """

    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()

    jobs: List[Job] = []

    for item in data:

        title = item.get("text", "").strip()
        url_ = item.get("hostedUrl", "").strip()

        if not title or not url_:
            continue

        categories = item.get("categories", {}) or {}
        location = categories.get("location", "")

        description = _strip_html(
            item.get("descriptionPlain")
            or item.get("description", "")
        )

        jobs.append(
            Job(
                title=title,
                organization=company_name,
                url=url_,
                subject_areas="",
                description=(
                    f"Location: {location}\n{description}"
                    if location
                    else description
                ),
                position_type="",
                deadline="",
                source=f"Industry: {company_name}",
            )
        )

    return jobs


def fetch_smartrecruiters_jobs(
    company_name: str,
    company_id: str,
    timeout: int = 30,
    query: str = "research scientist",
) -> List[Job]:
    """
    Fetch job listings from a company's SmartRecruiters postings API.
    """

    url = (
        f"https://api.smartrecruiters.com/v1/companies/"
        f"{company_id}/postings"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        params={
            "limit": 100,
            "q": query,
        },
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()

    jobs: List[Job] = []

    for item in data.get("content", []):

        title = item.get("name", "").strip()
        posting_id = item.get("id", "")

        if not title or not posting_id:
            continue

        url_ = (
            f"https://jobs.smartrecruiters.com/"
            f"{company_id}/{posting_id}"
        )

        location_info = item.get("location", {}) or {}
        location = ", ".join(
            part
            for part in [
                location_info.get("city", ""),
                location_info.get("country", ""),
            ]
            if part
        )

        department = (
            item.get("department", {}) or {}
        ).get("label", "")

        jobs.append(
            Job(
                title=title,
                organization=company_name,
                url=url_,
                subject_areas=department,
                description=(
                    f"Location: {location}" if location else ""
                ),
                position_type="",
                deadline="",
                source=f"Industry: {company_name}",
            )
        )

    return jobs


def fetch_amazon_science_jobs(
    timeout: int = 30,
    query: str = "research scientist",
) -> List[Job]:
    """
    Fetch job listings from Amazon's public jobs search API,
    scoped to Amazon Science / research roles.
    """

    url = "https://www.amazon.jobs/en/search.json"

    response = requests.get(
        url,
        headers=HEADERS,
        params={
            "base_query": query,
            "result_limit": 100,
            "sort": "recent",
        },
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()

    jobs: List[Job] = []

    for item in data.get("jobs", []):

        title = item.get("title", "").strip()
        job_path = item.get("job_path", "")

        if not title or not job_path:
            continue

        url_ = f"https://www.amazon.jobs{job_path}"

        location = item.get("location", "")

        description = item.get("description", "") or ""

        jobs.append(
            Job(
                title=title,
                organization="Amazon",
                url=url_,
                subject_areas="",
                description=(
                    f"Location: {location}\n{description}"
                    if location
                    else description
                ),
                position_type="",
                deadline="",
                source="Industry: Amazon Science",
            )
        )

    return jobs


def fetch_workday_jobs(
    company_name: str,
    tenant: str,
    host: str,
    site: str,
    timeout: int = 30,
    search_text: str = "research scientist",
    max_results: int = 20,
) -> List[Job]:
    """
    Fetch job listings from a company's Workday CXS job API.

    Workday's CXS endpoint caps "limit" at 20 per request and
    returns HTTP 400 above that, so max_results is not raised
    past 20 here.
    """

    api_url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"

    payload = {
        "appliedFacets": {},
        "limit": max_results,
        "offset": 0,
        "searchText": search_text,
    }

    response = requests.post(
        api_url,
        headers={
            **HEADERS,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()

    jobs: List[Job] = []

    for item in data.get("jobPostings", []):

        title = item.get("title", "").strip()
        external_path = item.get("externalPath", "")

        if not title or not external_path:
            continue

        url_ = f"https://{host}/{site}{external_path}"

        posted_on = item.get("postedOn", "")
        locations_text = item.get("locationsText", "")

        supporting_info = []

        if locations_text:
            supporting_info.append(f"Location: {locations_text}")

        if posted_on:
            supporting_info.append(f"Posted: {posted_on}")

        jobs.append(
            Job(
                title=title,
                organization=company_name,
                url=url_,
                subject_areas="",
                description="\n".join(supporting_info),
                position_type="",
                deadline="",
                source=f"Industry: {company_name}",
            )
        )

    return jobs


def fetch_jobs(
    timeout: int = 30,
    workday_search_text: str = "research scientist",
) -> List[Job]:
    """
    Fetch industry Research Scientist job listings from every
    configured source. Each source is isolated so a single
    failing/blocked company does not stop the others.
    """

    jobs: List[Job] = []

    for company_name, token in GREENHOUSE_BOARDS.items():

        try:
            jobs.extend(
                fetch_greenhouse_jobs(
                    company_name, token, timeout=timeout
                )
            )
        except requests.RequestException as error:
            print(f"  Could not read {company_name} (Greenhouse): {error}")

    for company_name, slug in LEVER_BOARDS.items():

        try:
            jobs.extend(
                fetch_lever_jobs(
                    company_name, slug, timeout=timeout
                )
            )
        except requests.RequestException as error:
            print(f"  Could not read {company_name} (Lever): {error}")

    for company_name, company_id in SMARTRECRUITERS_COMPANIES.items():

        try:
            jobs.extend(
                fetch_smartrecruiters_jobs(
                    company_name, company_id, timeout=timeout
                )
            )
        except requests.RequestException as error:
            print(
                f"  Could not read {company_name} "
                f"(SmartRecruiters): {error}"
            )

    try:
        jobs.extend(fetch_amazon_science_jobs(timeout=timeout))
    except requests.RequestException as error:
        print(f"  Could not read Amazon Science: {error}")

    for company_name, config in WORKDAY_BOARDS.items():

        try:
            jobs.extend(
                fetch_workday_jobs(
                    company_name,
                    config["tenant"],
                    config["host"],
                    config["site"],
                    timeout=timeout,
                    search_text=workday_search_text,
                )
            )
        except requests.RequestException as error:
            print(f"  Could not read {company_name} (Workday): {error}")

    return jobs
