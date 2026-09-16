from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from job_monitor.database.storage import get_all_jobs
from job_monitor.export.link_check import check_links

REQUIREMENT_HEADERS = [
    "required qualifications",
    "minimum qualifications",
    "basic qualifications",
    "preferred qualifications",
    "qualifications",
    "requirements",
]

STOP_HEADERS = [
    "how to apply",
    "application materials",
    "application instructions",
    "to apply",
    "about the department",
    "about the university",
    "about us",
    "responsibilities",
    "salary",
    "benefits",
    "equal employment",
    "eeo statement",
    "diversity statement",
]


def _extract_requirement(description: str, max_length: int = 500) -> str:
    """
    Best-effort extraction of a "requirements/qualifications" excerpt
    from a raw scraped job description. Descriptions are unstructured
    free text, so this is a heuristic, not a guarantee - it looks for
    the earliest common qualifications-style header and grabs the
    text up to the next likely section break.
    """

    if not description:
        return ""

    lower = description.lower()

    start = None

    for header in REQUIREMENT_HEADERS:
        pattern = re.compile(r"\b" + re.escape(header) + r"\b\s*[:\-]?\s*")
        match = pattern.search(lower)

        if match and (start is None or match.start() < start[0]):
            start = (match.start(), match.end())

    if start is None:
        return ""

    remainder = description[start[1]:]
    remainder_lower = remainder.lower()

    end = len(remainder)

    for stop in STOP_HEADERS:
        idx = remainder_lower.find(stop)
        if idx != -1 and idx < end:
            end = idx

    excerpt = remainder[: min(end, max_length)].strip()

    if end > max_length:
        excerpt += "..."

    return excerpt


def _short_description(description: str, max_length: int = 300) -> str:

    if not description:
        return ""

    cleaned = " ".join(description.split())

    if len(cleaned) <= max_length:
        return cleaned

    truncated = cleaned[:max_length].rsplit(" ", 1)[0]

    return truncated + "..."


def generate_excel_report(
    output_path: str = "reports/all_postings.xlsx",
    verify_links: bool = True,
) -> Path:
    """
    Export every posting ever saved (CORE/BROAD/ADJACENT, old and new)
    to an Excel file. Short Description and Requirement are only as
    good as the description text captured for that posting - older
    entries scraped before description storage was added, or
    postings that have since been taken down and never re-scraped,
    may have those two columns blank.

    When verify_links is True (the default), every URL is actually
    fetched to confirm it's still live and, if no deadline was ever
    captured, to try to find one on the page. This is what catches
    cases like a department's listing page still linking to a
    posting whose application system has already closed it (HTTP
    410) - without this check the export would silently repeat a
    stale link. It's a real network pass over every row, so it takes
    a while (roughly a few seconds per posting).
    """

    rows = get_all_jobs()

    if verify_links:

        def _progress(index, total, row):
            print(
                f"  Checking {index}/{total}: "
                f"[{row['link_status']}] {row['title'][:60]}"
            )

        rows = check_links(rows, progress_callback=_progress)

    records = []

    for row in rows:

        description = row.get("description") or ""

        records.append(
            {
                "University": row["organization"],
                "Position": row["title"],
                "Relevance": row["relevance_level"],
                "Link Status": row.get("link_status", "Not checked"),
                "Short Description": _short_description(description),
                "Requirement": _extract_requirement(description),
                "Deadline": row["deadline"] or "",
                "Submission Link": row["url"],
                "First Seen": (row["first_seen"] or "")[:10],
            }
        )

    columns = [
        "University",
        "Position",
        "Relevance",
        "Link Status",
        "Short Description",
        "Requirement",
        "Deadline",
        "Submission Link",
        "First Seen",
    ]

    dataframe = pd.DataFrame(records, columns=columns)

    # Live/unverified postings first, expired ones pushed to the
    # bottom so they don't clutter what's actually actionable.
    status_order = {"Live": 0, "Not checked": 1, "Unknown": 1, "Expired": 2}
    dataframe["_sort_key"] = dataframe["Link Status"].map(
        lambda status: status_order.get(status, 1)
    )
    dataframe = dataframe.sort_values(
        ["_sort_key", "University"]
    ).drop(columns="_sort_key")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:

        dataframe.to_excel(writer, index=False, sheet_name="Postings")

        worksheet = writer.sheets["Postings"]
        worksheet.freeze_panes = "A2"

        column_widths = {
            "A": 34,
            "B": 48,
            "C": 12,
            "D": 14,
            "E": 60,
            "F": 55,
            "G": 16,
            "H": 55,
            "I": 12,
        }

        for column_letter, width in column_widths.items():
            worksheet.column_dimensions[column_letter].width = width

    return path


if __name__ == "__main__":
    saved_path = generate_excel_report()
    print(f"Saved {saved_path}")
