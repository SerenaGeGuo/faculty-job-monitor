from __future__ import annotations

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


TEST_URLS = {
    "today": "https://www.higheredjobs.com/search/today.cfm",
    "detail": "https://www.higheredjobs.com/faculty/details.cfm?JobCode=179390118",
}


def test_access(timeout: int = 30):
    """
    Test whether HigherEdJobs pages can be accessed
    using a normal requests session.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    for name, url in TEST_URLS.items():

        print("=" * 70)
        print(f"Testing: {name}")
        print(f"URL: {url}")

        try:
            response = session.get(
                url,
                timeout=timeout,
            )

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

            iframes = soup.find_all("iframe")
            links = soup.find_all("a", href=True)

            print(
                f"HTML length: {len(response.text)}"
            )

            print(
                f"Visible text length: {len(text)}"
            )

            print(
                f"Number of iframes: {len(iframes)}"
            )

            print(
                f"Number of links: {len(links)}"
            )

            if iframes:
                print("Iframe sources:")

                for iframe in iframes:
                    print(
                        "  ",
                        iframe.get("src", "")
                    )

            if (
                "security check" in text.lower()
                or "_incapsula_resource"
                in response.url.lower()
            ):
                print(
                    "RESULT: BLOCKED BY SECURITY CHECK"
                )

            elif iframes and len(text) < 100:
                print(
                    "RESULT: OUTER PAGE ONLY - CONTENT IS IN IFRAME"
                )

            elif len(text) < 100:
                print(
                    "RESULT: PAGE LOADED BUT USEFUL CONTENT NOT PRESENT"
                )

            else:
                print(
                    "RESULT: PAGE CONTENT ACCESSIBLE"
                )

            print(
                "First 300 visible characters:"
            )

            print(
                text[:300]
            )

        except requests.RequestException as error:

            print(
                f"REQUEST ERROR: {error}"
            )