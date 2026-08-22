from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import List, Tuple

from dotenv import load_dotenv

load_dotenv()

DEFAULT_SMTP_HOST = "smtp.office365.com"
DEFAULT_SMTP_PORT = 587


def is_email_configured() -> bool:
    """
    Email sending is optional. It's considered configured only when
    both SMTP_USERNAME and SMTP_PASSWORD are present in the
    environment (typically loaded from a local .env file).
    """

    return bool(
        os.environ.get("SMTP_USERNAME")
        and os.environ.get("SMTP_PASSWORD")
    )


def _format_job_line(result, job) -> str:

    status = "NEW" if result.get("is_new") else "SEEN"

    deadline = job.deadline.strip() or "no listed deadline"

    return (
        f"  [{status}] {job.title}\n"
        f"    Organization: {job.organization}\n"
        f"    Source: {job.source}\n"
        f"    Deadline: {deadline}\n"
        f"    URL: {job.url}\n"
    )


def build_digest_text(
    matches: List[Tuple[dict, object]],
) -> str:
    """
    Build a plain-text weekly digest, prioritizing NEW postings but
    including full counts for context.
    """

    new_matches = [item for item in matches if item[0]["is_new"]]

    core = [item for item in matches if item[0]["level"] == "CORE"]
    broad = [item for item in matches if item[0]["level"] == "BROAD"]
    adjacent = [
        item for item in matches if item[0]["level"] == "ADJACENT"
    ]

    new_core = [item for item in new_matches if item[0]["level"] == "CORE"]
    new_broad = [item for item in new_matches if item[0]["level"] == "BROAD"]
    new_adjacent = [
        item for item in new_matches if item[0]["level"] == "ADJACENT"
    ]

    lines = []

    lines.append(
        f"Faculty/Research Scientist Job Digest - "
        f"{datetime.now().strftime('%Y-%m-%d')}"
    )
    lines.append("")
    lines.append(
        f"New postings this run: {len(new_matches)} "
        f"(CORE {len(new_core)}, BROAD {len(new_broad)}, "
        f"ADJACENT {len(new_adjacent)})"
    )
    lines.append(
        f"Total matches on file: {len(matches)} "
        f"(CORE {len(core)}, BROAD {len(broad)}, "
        f"ADJACENT {len(adjacent)})"
    )
    lines.append("")

    if not new_matches:
        lines.append("No new postings since the last run.")
        lines.append("")

    for label, group in (
        ("NEW - CORE", new_core),
        ("NEW - BROAD", new_broad),
        ("NEW - ADJACENT", new_adjacent),
    ):

        if not group:
            continue

        lines.append(f"=== {label} ({len(group)}) ===")

        for result, job in group:
            lines.append(_format_job_line(result, job))

    return "\n".join(lines)


def send_digest_email(body: str, subject: str = None) -> bool:
    """
    Send the weekly digest by SMTP. Returns True if sent, False if
    email is not configured (SMTP_USERNAME/SMTP_PASSWORD missing) or
    if sending failed - callers should treat either as non-fatal.
    """

    if not is_email_configured():
        print(
            "\nEmail not configured (missing SMTP_USERNAME/"
            "SMTP_PASSWORD in .env) - skipping email digest."
        )
        return False

    smtp_host = os.environ.get("SMTP_HOST", DEFAULT_SMTP_HOST)
    smtp_port = int(os.environ.get("SMTP_PORT", DEFAULT_SMTP_PORT))
    username = os.environ["SMTP_USERNAME"]

    # Gmail displays app passwords as four space-separated groups
    # for readability; strip any whitespace so a direct copy-paste
    # doesn't break SMTP AUTH.
    password = os.environ["SMTP_PASSWORD"].replace(" ", "")

    sender = os.environ.get("EMAIL_FROM", username)
    recipient = os.environ.get("EMAIL_TO", "gguo28@wisc.edu")

    if subject is None:
        subject = (
            f"Faculty/Research Scientist Job Digest - "
            f"{datetime.now().strftime('%Y-%m-%d')}"
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(message)

    except Exception as error:
        print(f"\nCould not send digest email: {error}")
        return False

    print(f"\nDigest email sent to {recipient}")
    return True
