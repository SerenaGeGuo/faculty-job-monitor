from __future__ import annotations

from urllib.parse import urljoin
import html
import re

import requests
from bs4 import BeautifulSoup

from job_monitor.scrapers.academic_jobs_online import Job

JOBS_API_URL = (
    "https://careercenter.cra.org/"
    "api/v1/jobs"
)

BASE_URL = "https://careercenter.cra.org"

TEST_URLS = {
    "all_jobs": "https://careercenter.cra.org/jobs",
    "computer_science": (
        "https://careercenter.cra.org/"
        "c-computer-science-engineering-jobs.html"
    ),
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


def test_access(timeout: int = 30):
    """
    Test whether CRA Career Center pages can be accessed
    and inspect the links returned in the HTML.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    for name, url in TEST_URLS.items():

        print("=" * 70)
        print(f"Testing CRA page: {name}")
        print(f"URL: {url}")

        try:
            response = session.get(
                url,
                timeout=timeout,
            )

            response.raise_for_status()

        except requests.RequestException as error:

            print(
                f"REQUEST ERROR: {error}"
            )

            continue

        print(
            f"Status code: "
            f"{response.status_code}"
        )

        print(
            f"Final URL: "
            f"{response.url}"
        )

        soup = BeautifulSoup(
            response.text,
            "lxml",
        )

        title = (
            soup.title.get_text(
                " ",
                strip=True,
            )
            if soup.title
            else ""
        )

        print(
            f"Page title: {title}"
        )

        text = soup.get_text(
            " ",
            strip=True,
        )

        links = soup.find_all(
            "a",
            href=True,
        )

        print(
            f"HTML length: "
            f"{len(response.text)}"
        )

        print(
            f"Visible text length: "
            f"{len(text)}"
        )

        print(
            f"Number of links: "
            f"{len(links)}"
        )

        print(
            "\nFirst 500 visible characters:"
        )

        print(
            text[:500]
        )

        # -----------------------------------------------------
        # Find links that may represent individual jobs.
        # -----------------------------------------------------

        candidate_links = []
        seen_urls = set()

        for link in links:

            href = link.get(
                "href",
                "",
            )

            link_text = link.get_text(
                " ",
                strip=True,
            )

            if not href:
                continue

            full_url = urljoin(
                BASE_URL,
                href,
            )

            if full_url in seen_urls:
                continue

            # Keep potentially useful job-related links.
            href_lower = href.lower()

            if (
                "job" not in href_lower
                and "position" not in href_lower
            ):
                continue

            if not link_text:
                continue

            seen_urls.add(full_url)

            candidate_links.append(
                (
                    link_text,
                    full_url,
                )
            )

        print(
            f"\nCandidate job links found: "
            f"{len(candidate_links)}"
        )

        print(
            "\nFirst 20 candidate links:"
        )

        for link_text, full_url in candidate_links[:20]:

            print("-" * 70)

            print(
                f"Text: {link_text}"
            )

            print(
                f"URL: {full_url}"
            )




def test_dynamic_structure(timeout: int = 30):
    """
    Inspect the CRA jobs page to determine how the
    JavaScript-loaded job results are retrieved.
    """

    url = TEST_URLS["all_jobs"]

    print("=" * 70)
    print("Inspecting CRA dynamic job loading")
    print(f"URL: {url}")

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(
            url,
            timeout=timeout,
        )

        response.raise_for_status()

    except requests.RequestException as error:
        print(f"REQUEST ERROR: {error}")
        return

    soup = BeautifulSoup(
        response.text,
        "lxml",
    )

    raw_html = response.text

    # ---------------------------------------------------------
    # 1. Check whether individual /job/ URLs are already
    #    hidden somewhere in the raw HTML.
    # ---------------------------------------------------------

    job_url_matches = re.findall(
        r'https?://[^"\']+/job/[^"\']+',
        raw_html,
        re.IGNORECASE,
    )

    relative_job_matches = re.findall(
        r'["\'](/job/[^"\']+)["\']',
        raw_html,
        re.IGNORECASE,
    )

    print(
        f"\nAbsolute /job/ URLs in raw HTML: "
        f"{len(job_url_matches)}"
    )

    for item in job_url_matches[:10]:
        print(f"  {item[:200]}")

    print(
        f"\nRelative /job/ URLs in raw HTML: "
        f"{len(relative_job_matches)}"
    )

    for item in relative_job_matches[:10]:
        print(f"  {item[:200]}")

    # ---------------------------------------------------------
    # 2. Print external JavaScript files.
    # ---------------------------------------------------------

    scripts = soup.find_all(
        "script",
    )

    external_scripts = []

    for script in scripts:

        src = script.get(
            "src",
            "",
        )

        if not src:
            continue

        full_url = urljoin(
            BASE_URL,
            src,
        )

        external_scripts.append(
            full_url
        )

    print(
        f"\nExternal script files: "
        f"{len(external_scripts)}"
    )

    for script_url in external_scripts:

        print(
            f"  {script_url}"
        )

    # ---------------------------------------------------------
    # 3. Look for useful clues inside inline JavaScript.
    # ---------------------------------------------------------

    keywords = [
        "fetch(",
        "ajax",
        "axios",
        "/api/",
        "jobsearch",
        "job-search",
        "searchjobs",
        "search-jobs",
        "webscribble",
    ]

    print(
        "\nInteresting inline JavaScript:"
    )

    found_inline = False

    for script in scripts:

        if script.get("src"):
            continue

        script_text = script.get_text(
            " ",
            strip=True,
        )

        if not script_text:
            continue

        lower_script = script_text.lower()

        if not any(
            keyword in lower_script
            for keyword in keywords
        ):
            continue

        found_inline = True

        print("-" * 70)

        print(
            script_text[:1500]
        )

    if not found_inline:

        print(
            "No obvious API/AJAX code "
            "found in inline scripts."
        )

    # ---------------------------------------------------------
    # 4. Count useful markers in the raw HTML.
    # ---------------------------------------------------------

    print(
        "\nRaw HTML marker counts:"
    )

    markers = [
        "/job/",
        "api",
        "ajax",
        "webscribble",
        "loading",
    ]

    lower_html = raw_html.lower()

    for marker in markers:

        print(
            f"  {marker}: "
            f"{lower_html.count(marker)}"
        )



def test_listings_script(timeout: int = 30):
    """
    Inspect CRA's listings JavaScript to identify
    the API/AJAX endpoint used to load jobs.
    """

    script_url = (
        "https://careercenter.cra.org/"
        "themes/cra1/js/pages/"
        "_listings.js?1785924141"
    )

    print("=" * 70)
    print("Inspecting CRA _listings.js")
    print(f"URL: {script_url}")

    try:
        response = requests.get(
            script_url,
            headers=HEADERS,
            timeout=timeout,
        )

        response.raise_for_status()

    except requests.RequestException as error:
        print(f"REQUEST ERROR: {error}")
        return

    script_text = response.text

    print(
        f"\nStatus code: "
        f"{response.status_code}"
    )

    print(
        f"Script length: "
        f"{len(script_text)}"
    )

    # ---------------------------------------------------------
    # Search for terms that may reveal how jobs are loaded.
    # ---------------------------------------------------------

    keywords = [
        "ajax",
        "fetch",
        "url",
        "route",
        "ziggy",
        "api",
        "listing",
        "search",
        "$.get",
        "$.post",
    ]

    print("\nKeyword occurrences:")

    lower_text = script_text.lower()

    for keyword in keywords:

        print(
            f"  {keyword}: "
            f"{lower_text.count(keyword.lower())}"
        )

    # ---------------------------------------------------------
    # Print lines containing useful clues.
    # ---------------------------------------------------------

    print(
        "\nPotentially useful lines:"
    )

    useful_lines = []

    for line in script_text.splitlines():

        lower_line = line.lower()

        if any(
            keyword.lower() in lower_line
            for keyword in keywords
        ):
            useful_lines.append(
                line.strip()
            )

    for line in useful_lines:

        print("-" * 70)
        print(line)

    # ---------------------------------------------------------
    # Also print the complete script.
    #
    # _listings.js is relatively small, so seeing all of it
    # may reveal route construction that keyword matching misses.
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("FULL _listings.js")
    print("=" * 70)

    print(script_text)



def test_listings_api(timeout: int = 30):
    """
    Find the concrete URL for CRA's api.listings route
    and test whether it returns job data directly.
    """

    jobs_url = TEST_URLS["all_jobs"]

    print("=" * 70)
    print("Finding CRA api.listings endpoint")
    print(f"Jobs page: {jobs_url}")

    session = requests.Session()

    session.headers.update(
        {
            **HEADERS,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": jobs_url,
        }
    )

    # ---------------------------------------------------------
    # 1. Download the jobs page and locate the named route.
    # ---------------------------------------------------------

    try:
        response = session.get(
            jobs_url,
            timeout=timeout,
        )

        response.raise_for_status()

    except requests.RequestException as error:
        print(f"REQUEST ERROR: {error}")
        return

    raw_html = response.text

    print(
        f"\nOccurrences of api.listings: "
        f"{raw_html.count('api.listings')}"
    )

    # ---------------------------------------------------------
    # 2. Print HTML around api.listings.
    #    This helps us inspect the Ziggy route definition.
    # ---------------------------------------------------------

    position = raw_html.find(
        "api.listings"
    )

    if position != -1:

        start = max(
            0,
            position - 500,
        )

        end = min(
            len(raw_html),
            position + 1000,
        )

        print(
            "\nHTML around api.listings:"
        )

        print("-" * 70)

        print(
            raw_html[start:end]
        )

    # ---------------------------------------------------------
    # 3. Try to extract the route URI automatically.
    #
    # Typical Laravel/Ziggy structure:
    #
    # "api.listings":{"uri":"api/listings", ...}
    # ---------------------------------------------------------

    patterns = [
        (
            r'"api\.listings"\s*:\s*'
            r'\{\s*"uri"\s*:\s*"([^"]+)"'
        ),
        (
            r"'api\.listings'\s*:\s*"
            r"\{\s*'uri'\s*:\s*'([^']+)'"
        ),
    ]

    route_uri = ""

    for pattern in patterns:

        match = re.search(
            pattern,
            raw_html,
        )

        if match:
            route_uri = match.group(1)

            # CRA stores URLs in JavaScript as:
            # api\/v1\/listings
            # Convert escaped slashes back to normal slashes.
            route_uri = route_uri.replace(
                "\\/",
                "/",
            )

            break

    if not route_uri:

        print(
            "\nCould not automatically extract "
            "api.listings URI."
        )

        return

    print(
        f"\nRoute URI found: "
        f"{route_uri}"
    )

    # ---------------------------------------------------------
    # 4. Convert the route into a full URL.
    # ---------------------------------------------------------

    api_url = urljoin(
        BASE_URL + "/",
        route_uri,
    )

    print(
        f"API URL: "
        f"{api_url}"
    )

    # ---------------------------------------------------------
    # 5. Call the listings API directly.
    # ---------------------------------------------------------

    try:
        api_response = session.get(
            api_url,
            params={
                "keywords": "",
                "categories": "",
            },
            timeout=timeout,
        )

    except requests.RequestException as error:

        print(
            f"\nAPI REQUEST ERROR: "
            f"{error}"
        )

        return

    print("\n" + "=" * 70)
    print("CRA LISTINGS API RESPONSE")
    print("=" * 70)

    print(
        f"Status code: "
        f"{api_response.status_code}"
    )

    print(
        f"Content-Type: "
        f"{api_response.headers.get('Content-Type', '')}"
    )

    print(
        f"Response length: "
        f"{len(api_response.text)}"
    )

    print(
        "\nFirst 1000 response characters:"
    )

    print(
        api_response.text[:1000]
    )

    # ---------------------------------------------------------
    # 6. If JSON works, inspect its structure.
    # ---------------------------------------------------------

    try:
        data = api_response.json()

    except ValueError:

        print(
            "\nResponse is not valid JSON."
        )

        return

    print(
        "\nJSON top-level type: "
        f"{type(data).__name__}"
    )

    if isinstance(
        data,
        dict,
    ):

        print(
            f"Top-level keys: "
            f"{list(data.keys())}"
        )

        listings = data.get(
            "data",
            []
        )

        print(
            f"Listings returned: "
            f"{len(listings)}"
        )

        if listings:

            print(
                "\nFirst listing:"
            )

            first_listing = listings[0]

            if isinstance(
                first_listing,
                dict,
            ):

                for key, value in (
                    first_listing.items()
                ):

                    print(
                        f"{key}: "
                        f"{str(value)[:500]}"
                    )

            else:

                print(
                    first_listing
                )


def test_keyword_search(timeout: int = 30):
    """
    Test CRA's listings API using actual job-search keywords.
    """

    api_url = (
        "https://careercenter.cra.org/"
        "api/v1/listings"
    )

    session = requests.Session()

    session.headers.update(
        {
            **HEADERS,
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": (
                "https://careercenter.cra.org/jobs"
            ),
        }
    )

    test_keywords = [
        "assistant professor",
        "professor",
        "faculty",
        "computer science",
    ]

    for keyword in test_keywords:

        print("\n" + "=" * 70)
        print(
            f"Testing CRA keyword: "
            f"{keyword}"
        )
        print("=" * 70)

        try:
            response = session.get(
                api_url,
                params={
                    "keywords": keyword,
                    "categories": "",
                },
                timeout=timeout,
            )

            response.raise_for_status()

        except requests.RequestException as error:

            print(
                f"REQUEST ERROR: {error}"
            )

            continue

        print(
            f"Final URL: "
            f"{response.url}"
        )

        print(
            f"Status code: "
            f"{response.status_code}"
        )

        try:
            data = response.json()

        except ValueError:

            print(
                "Response is not valid JSON."
            )

            print(
                response.text[:500]
            )

            continue

        listings = data.get(
            "data",
            []
        )

        print(
            f"Listings returned: "
            f"{len(listings)}"
        )

        # Show up to the first 3 listings.
        for index, listing in enumerate(
            listings[:3],
            start=1,
        ):

            print(
                "\n" + "-" * 70
            )

            print(
                f"LISTING {index}"
            )

            if isinstance(
                listing,
                dict,
            ):

                for key, value in (
                    listing.items()
                ):

                    print(
                        f"{key}: "
                        f"{str(value)[:500]}"
                    )

            else:

                print(
                    listing
                )


def test_job_route_calls(timeout: int = 30):
    """
    Inspect CRA's JavaScript and route table to identify
    the API used for the main job-search results.
    """

    jobs_url = TEST_URLS["all_jobs"]

    session = requests.Session()
    session.headers.update(HEADERS)

    print("=" * 70)
    print("Inspecting CRA job/search routes")
    print(f"URL: {jobs_url}")

    try:
        response = session.get(
            jobs_url,
            timeout=timeout,
        )

        response.raise_for_status()

    except requests.RequestException as error:
        print(f"REQUEST ERROR: {error}")
        return

    raw_html = response.text

    # =========================================================
    # 1. Extract relevant routes from CRA's Ziggy route table
    # =========================================================

    print("\n" + "=" * 70)
    print("RELEVANT ROUTES DEFINED IN PAGE")
    print("=" * 70)

    route_pattern = re.compile(
        r'"([^"]+)"\s*:\s*'
        r'\{\s*"uri"\s*:\s*"([^"]+)"'
    )

    relevant_terms = [
        "job",
        "jobs",
        "listing",
        "listings",
        "search",
    ]

    defined_routes = []

    for match in route_pattern.finditer(
        raw_html
    ):

        route_name = match.group(1)

        route_uri = (
            match.group(2)
            .replace("\\/", "/")
        )

        combined = (
            route_name.lower()
            + " "
            + route_uri.lower()
        )

        if not any(
            term in combined
            for term in relevant_terms
        ):
            continue

        defined_routes.append(
            (
                route_name,
                route_uri,
            )
        )

    for route_name, route_uri in defined_routes:

        print("-" * 70)
        print(f"NAME: {route_name}")
        print(f"URI:  {route_uri}")

    print(
        f"\nRelevant route definitions found: "
        f"{len(defined_routes)}"
    )

    # =========================================================
    # 2. Find all CRA-hosted JavaScript files
    # =========================================================

    soup = BeautifulSoup(
        raw_html,
        "lxml",
    )

    script_urls = []

    for script in soup.find_all(
        "script",
        src=True,
    ):

        script_url = urljoin(
            BASE_URL,
            script["src"],
        )

        if not script_url.startswith(
            BASE_URL
        ):
            continue

        script_urls.append(
            script_url
        )

    print("\n" + "=" * 70)
    print("SEARCHING CRA JAVASCRIPT")
    print("=" * 70)

    # =========================================================
    # 3. Search each JS file for route("...")
    # =========================================================

    route_call_pattern = re.compile(
        r'route\(\s*["\']([^"\']+)["\']'
    )

    all_route_calls = {}

    for script_url in script_urls:

        try:
            script_response = session.get(
                script_url,
                timeout=timeout,
            )

            script_response.raise_for_status()

        except requests.RequestException:
            continue

        script_text = script_response.text

        route_calls = set(
            route_call_pattern.findall(
                script_text
            )
        )

        relevant_calls = []

        for route_name in route_calls:

            route_lower = (
                route_name.lower()
            )

            if any(
                term in route_lower
                for term in relevant_terms
            ):
                relevant_calls.append(
                    route_name
                )

        if relevant_calls:

            all_route_calls[
                script_url
            ] = sorted(
                relevant_calls
            )

    for script_url, route_calls in (
        all_route_calls.items()
    ):

        print("\n" + "-" * 70)
        print(f"SCRIPT: {script_url}")

        for route_name in route_calls:
            print(
                f"  route('{route_name}')"
            )

    # =========================================================
    # 4. Search scripts for literal API URLs as a fallback
    # =========================================================

    print("\n" + "=" * 70)
    print("LITERAL API PATHS FOUND IN JAVASCRIPT")
    print("=" * 70)

    api_paths = set()

    api_pattern = re.compile(
        r'api(?:\\/|/)v1(?:\\/|/)'
        r'[A-Za-z0-9_\-./{}]+'
    )

    for script_url in script_urls:

        try:
            script_response = session.get(
                script_url,
                timeout=timeout,
            )

            script_response.raise_for_status()

        except requests.RequestException:
            continue

        for match in api_pattern.findall(
            script_response.text
        ):

            clean_path = match.replace(
                "\\/",
                "/",
            )

            api_paths.add(
                clean_path
            )

    for path in sorted(api_paths):
        print(
            f"  {path}"
        )



def _get_custom_value(
    listing,
    label,
):
    """
    Get a value such as Position Type from CRA's
    customBlockList.
    """

    blocks = listing.get(
        "customBlockList",
        [],
    )

    for block in blocks:

        if block.get("label") == label:

            value = block.get(
                "value",
                "",
            )

            return html.unescape(
                str(value)
            ).strip()

    return ""


def fetch_jobs(
    timeout: int = 30,
    max_pages: int = 10,
):
    """
    Fetch jobs from the CRA Career Center JSON API
    and convert them to the shared Job format.
    """

    session = requests.Session()

    session.headers.update(
        {
            **HEADERS,
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": (
                "https://careercenter.cra.org/jobs"
            ),
        }
    )

    jobs = []
    seen_urls = set()

    page = 1

    while page <= max_pages:

        print(
            f"Reading CRA jobs page "
            f"{page}..."
        )

        try:
            response = session.get(
                JOBS_API_URL,
                params={
                    "locale": "en",
                    "page": page,
                    "sort": "date",
                },
                timeout=timeout,
            )

            response.raise_for_status()

        except requests.RequestException as error:

            print(
                f"Could not read CRA page: "
                f"{error}"
            )

            break

        try:
            payload = response.json()

        except ValueError:

            print(
                "CRA response was not "
                "valid JSON."
            )

            break

        listings = payload.get(
            "data",
            [],
        )

        print(
            f"Jobs returned: "
            f"{len(listings)}"
        )

        for listing in listings:

            title = html.unescape(
                listing.get(
                    "title",
                    "",
                )
            ).strip()

            url = listing.get(
                "url",
                "",
            ).strip()

            if (
                not title
                or not url
                or url in seen_urls
            ):
                continue

            company = (
                listing.get("company")
                or {}
            )

            organization = html.unescape(
                company.get(
                    "name",
                    "",
                )
            ).strip()

            short_description = html.unescape(
                listing.get(
                    "shortDescription",
                    "",
                )
            )

            # Remove any HTML tags that may occur
            # inside CRA's short description.
            description = BeautifulSoup(
                short_description,
                "lxml",
            ).get_text(
                " ",
                strip=True,
            )

            location = html.unescape(
                listing.get(
                    "location",
                    "",
                )
            ).strip()

            posted_date = listing.get(
                "posted_date",
                "",
            ).strip()

            position_type = _get_custom_value(
                listing,
                "Position Type",
            )

            # Keep location and posting date in the
            # description for now because our shared
            # Job model does not yet have dedicated
            # fields for them.
            supporting_info = []

            if location:
                supporting_info.append(
                    f"Location: {location}"
                )

            if posted_date:
                supporting_info.append(
                    f"Posted: {posted_date}"
                )

            if supporting_info:

                description = (
                    description
                    + "\n"
                    + "\n".join(
                        supporting_info
                    )
                )

            job = Job(
                title=title,
                organization=organization,
                url=url,
                subject_areas="",
                description=description,
                position_type=position_type,
                deadline="",
                source="CRA",
            )

            jobs.append(job)
            seen_urls.add(url)

        meta = payload.get(
            "meta",
            {},
        )

        last_page = meta.get(
            "last_page",
            page,
        )

        if page >= last_page:
            break

        page += 1

    print(
        f"\nTotal CRA jobs collected: "
        f"{len(jobs)}"
    )

    return jobs