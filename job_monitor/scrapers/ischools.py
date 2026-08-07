from __future__ import annotations

from urllib.parse import urljoin
from datetime import datetime
import re

import requests
from bs4 import BeautifulSoup

from job_monitor.scrapers.academic_jobs_online import Job

BASE_URL = "https://www.ischools.org"
JOBS_URL = "https://www.ischools.org/news/categories/jobs"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


def fetch_post_links(
    timeout: int = 30,
    max_pages: int = 5,
):
    """
    Collect individual iSchools job-post links
    from the Jobs category pages.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    posts = []
    seen_urls = set()

    for page_number in range(
        1,
        max_pages + 1,
    ):

        if page_number == 1:
            page_url = JOBS_URL

        else:
            page_url = (
                f"{JOBS_URL}/page/"
                f"{page_number}"
            )

        print("=" * 70)
        print(
            f"Reading iSchools Jobs page "
            f"{page_number}/{max_pages}"
        )
        print(f"URL: {page_url}")

        try:
            response = session.get(
                page_url,
                timeout=timeout,
            )

            response.raise_for_status()

        except requests.RequestException as error:

            print(
                f"Could not read page: {error}"
            )

            continue

        soup = BeautifulSoup(
            response.text,
            "lxml",
        )

        page_posts = []

        for link in soup.find_all(
            "a",
            href=True,
        ):

            href = link.get(
                "href",
                "",
            )

            if "/post/" not in href:
                continue

            full_url = urljoin(
                BASE_URL,
                href,
            )

            # Remove query parameters, if any.
            full_url = (
                full_url
                .split("?")[0]
                .rstrip("/")
            )

            # Keep only actual iSchools post pages.
            if not full_url.startswith(
                f"{BASE_URL}/post/"
            ):
                continue

            if full_url in seen_urls:
                continue

            title = link.get_text(
                " ",
                strip=True,
            )

            # Ignore image-only links that have
            # no useful visible title.
            if not title:
                continue

            seen_urls.add(full_url)

            post = {
                "title": title,
                "url": full_url,
            }

            posts.append(post)
            page_posts.append(post)

        print(
            f"New post links found on page: "
            f"{len(page_posts)}"
        )

        for post in page_posts:

            print(
                f"  - {post['title']}"
            )

    return posts

def extract_job_description(page_text):
    """
    Extract only the actual job description from an
    iSchools post, removing site navigation, deadline,
    and footer text.
    """

    lines = [
        line.strip()
        for line in page_text.splitlines()
        if line.strip()
    ]

    start_index = None
    end_index = None

    for index, line in enumerate(lines):

        if line.lower().startswith(
            "application deadline:"
        ):

            start_index = index + 1

            # On iSchools, the label and deadline
            # are often on separate lines:
            #
            # Application Deadline:
            # September 7, 2026
            #
            # Skip the deadline value as well.
            if (
                line.strip()
                .lower()
                .rstrip(":")
                == "application deadline"
            ):
                start_index += 1

            break

    if start_index is None:
        start_index = 0

    for index in range(
        start_index,
        len(lines),
    ):

        if lines[index].lower() == "read more":
            end_index = index
            break

    if end_index is None:
        end_index = len(lines)

    description_lines = lines[
        start_index:end_index
    ]

    return "\n".join(
        description_lines
    ).strip()


def normalize_deadline(deadline):
    """
    Convert iSchools deadline text into YYYY/MM/DD
    so the main monitor can compare dates consistently.

    Open-until-filled positions are returned as "none".
    """

    text = deadline.strip()

    if not text:
        return ""

    lower_text = text.lower()

    # Keep open-ended searches active.
    if "until filled" in lower_text:
        return "none"

    # Find natural-language dates such as:
    # September 7, 2026
    # 11:59 pm on August 7, 2026
    month_pattern = (
        r"\b("
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December"
        r")\s+(\d{1,2}),\s+(20\d{2})\b"
    )

    match = re.search(
        month_pattern,
        text,
        re.IGNORECASE,
    )

    if match:

        month_name = match.group(1)
        day = match.group(2)
        year = match.group(3)

        parsed_date = datetime.strptime(
            f"{month_name} {day} {year}",
            "%B %d %Y",
        )

        return parsed_date.strftime(
            "%Y/%m/%d"
        )

    # If we do not recognize the format,
    # keep the original text rather than losing it.
    return text

def extract_organization(
    description,
    page_text,
):
    """
    Extract the university or institution name from
    an iSchools job post.
    """

    lines = [
        line.strip()
        for line in page_text.splitlines()
        if line.strip()
    ]

    # ---------------------------------------------------------
    # Strategy 1:
    # Some iSchools pages put the institution directly
    # above "Application Deadline".
    # ---------------------------------------------------------

    for index, line in enumerate(lines):

        if not line.lower().startswith(
            "application deadline:"
        ):
            continue

        if index == 0:
            break

        candidate = lines[index - 1]

        candidate_lower = candidate.lower()

        institution_terms = [
            "university",
            "college",
            "institute",
        ]

        if (
            any(
                term in candidate_lower
                for term in institution_terms
            )
            and len(candidate) < 150
        ):
            return candidate

        break

    # ---------------------------------------------------------
    # Strategy 2:
    # Look in the beginning of the actual job description.
    #
    # Examples:
    # "at San José State University"
    # "at the University of Oklahoma"
    # "at University of Wisconsin-Madison"
    # ---------------------------------------------------------

    preview = description[:1500]

    patterns = [
        (
            r"\bat (?:the )?"
            r"((?:University|College|Institute) "
            r"of [A-Z][A-Za-zÀ-ÿ0-9&.'’\-, ]+?)"
            r"(?=\s*(?:\(|is|invites|seeks|,|\n))"
        ),
        (
            r"\bat (?:the )?"
            r"([A-Z][A-Za-zÀ-ÿ0-9&.'’\-, ]+?"
            r"(?:University|College|Institute))"
            r"(?=\s*(?:\(|is|invites|seeks|,|\n))"
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            preview,
        )

        if match:
            return (
                match.group(1)
                .strip(" ,.")
            )

    # ---------------------------------------------------------
    # Strategy 3:
    # Some descriptions begin directly with the institution.
    #
    # Example:
    # "Western University invites applications..."
    # ---------------------------------------------------------

    first_line = (
        description.splitlines()[0]
        if description
        else ""
    )

    match = re.match(
        r"^("
        r"[A-Z][A-Za-zÀ-ÿ0-9&.'’\-, ]+?"
        r"(?:University|College|Institute)"
        r")\b",
        first_line,
    )

    if match:
        return (
            match.group(1)
            .strip(" ,.")
        )

    return ""


def fetch_post_details(
    post,
    timeout: int = 30,
):
    """
    Read an individual iSchools job post
    and extract useful job information.
    """

    url = post["url"]

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=timeout,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "lxml",
    )

    # ---------------------------------------------------------
    # Title
    # ---------------------------------------------------------

    h1 = soup.find("h1")

    if h1:
        title = h1.get_text(
            " ",
            strip=True,
        )
    else:
        title = post["title"]

    # ---------------------------------------------------------
    # Visible page text
    # ---------------------------------------------------------

    page_text = soup.get_text(
        "\n",
        strip=True,
    )

    # ---------------------------------------------------------
    # Application deadline
    # ---------------------------------------------------------

    deadline = ""

    deadline_match = re.search(
        r"Application Deadline:\s*([^\n]+)",
        page_text,
        re.IGNORECASE,
    )

    if deadline_match:
        deadline = (
            deadline_match
            .group(1)
            .strip()
        )
    deadline = normalize_deadline(
        deadline
    )
    # ---------------------------------------------------------
    # External / official job link
    # ---------------------------------------------------------

    external_url = ""

    for link in soup.find_all(
        "a",
        href=True,
    ):

        text = link.get_text(
            " ",
            strip=True,
        )

        if text.lower() == "read more":

            external_url = link.get(
                "href",
                "",
            )

            break

    # ---------------------------------------------------------
    # Description
    #
    # For now we keep the visible text.
    # We will clean navigation/footer text later.
    # ---------------------------------------------------------

    description = extract_job_description(
    page_text
    )   

    organization = extract_organization(
        description,
        page_text,
    )

    return {
        "title": title,
        "organization": organization,
        "url": url,
        "deadline": deadline,
        "external_url": external_url,
        "description": description,
    }

def fetch_jobs(
    timeout: int = 30,
    max_pages: int = 5,
):
    """
    Fetch iSchools job posts and convert them into
    the same Job format used by AcademicJobsOnline.
    """

    posts = fetch_post_links(
        timeout=timeout,
        max_pages=max_pages,
    )

    jobs = []

    print("\nFetching iSchools job details...")

    for index, post in enumerate(
        posts,
        start=1,
    ):

        print(
            f"Reading iSchools job "
            f"{index}/{len(posts)}: "
            f"{post['title'][:60]}"
        )

        try:
            details = fetch_post_details(
                post,
                timeout=timeout,
            )

        except requests.RequestException as error:

            print(
                f"  Could not read job: "
                f"{error}"
            )

            continue

        # Prefer the university's official job URL.
        # Fall back to the iSchools post if there is
        # no external link.
        job_url = (
            details["external_url"]
            or details["url"]
        )

        job = Job(
            title=details["title"],
            organization=details["organization"],
            url=job_url,
            subject_areas="",
            description=details["description"],
            position_type="",
            deadline=details["deadline"],
            source="iSchools",
        )

        jobs.append(job)

    return jobs

def test_details():
    """
    Test detail extraction on the first five
    discovered iSchools job posts.
    """

    posts = fetch_post_links(
        max_pages=5,
    )

    print("\n" + "=" * 70)
    print("TESTING ISCHOOLS JOB DETAILS")
    print("=" * 70)

    for index, post in enumerate(
        posts[:5],
        start=1,
    ):

        print(
            f"\nReading detail "
            f"{index}/5..."
        )

        try:
            details = fetch_post_details(
                post
            )

        except requests.RequestException as error:

            print(
                f"Could not read job: "
                f"{error}"
            )

            continue

        print("\n" + "-" * 70)

        print(
            f"TITLE: "
            f"{details['title']}"
        )

        print(
            f"DEADLINE: "
            f"{details['deadline']}"
        )

        print(
            f"ISCHOOLS URL: "
            f"{details['url']}"
        )

        print(
            f"OFFICIAL URL: "
            f"{details['external_url']}"
        )

        print(
            "DESCRIPTION PREVIEW:"
        )

        print(
            details["description"][:500]
        )

def test_discovery():
    """
    Test iSchools job-post discovery
    across multiple pages.
    """

    posts = fetch_post_links()

    print("\n" + "=" * 70)
    print("ISCHOOLS DISCOVERY COMPLETE")
    print("=" * 70)

    print(
        f"\nTotal unique post links: "
        f"{len(posts)}"
    )

    print("\nAll discovered posts:")

    for index, post in enumerate(
        posts,
        start=1,
    ):

        print("\n" + "-" * 70)

        print(
            f"{index}. {post['title']}"
        )

        print(
            f"URL: {post['url']}"
        )