import yaml
import time
import re
from datetime import datetime

from job_monitor.scrapers.academic_jobs_online import (
    fetch_jobs,
    fetch_job_details,
)

from job_monitor.database.storage import (
    init_db,
    save_job,
)

def load_config():
    with open("config/search.yaml", "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def contains_any(text, keywords):
    text = text.lower()
    return any(keyword.lower() in text for keyword in keywords)


def score_job(job, config):
    text = f"{job.title} {job.organization}".lower()

    # Explicit exclusions
    if contains_any(job.title, config["exclude_titles"]):
        return None

    title_match = contains_any(
        job.title,
        config["faculty_titles"],
    )

    primary_match = contains_any(
        text,
        config["primary_keywords"],
    )

    secondary_match = contains_any(
        text,
        config["secondary_keywords"],
    )

    if title_match and primary_match:
        return "STRONG"

    if title_match and secondary_match:
        return "POSSIBLE"

    return None

def is_job_open(job):
    """
    Return False when the posting has an explicit application
    deadline that has already passed.
    """

    deadline_text = job.deadline.strip().lower()

    if not deadline_text or deadline_text == "none":
        return True

    match = re.search(
        r"\b(20\d{2})/(\d{2})/(\d{2})\b",
        deadline_text,
    )

    if not match:
        return True

    year, month, day = map(int, match.groups())

    deadline_date = datetime(
        year,
        month,
        day,
        23,
        59,
        59,
    )

    return datetime.now() <= deadline_date

def is_faculty_candidate(job):
    title = job.title.lower()

    # Reject positions that are clearly not our target
    exclude_terms = [
        "postdoc",
        "postdoctoral",
        "phd",
        "doctoral",
        "lecturer",
        "instructor",
        "adjunct",
        "visiting assistant professor",
        "visiting professor",
        "teaching professor",
        "teaching faculty",
        "non-tenure",
        "non tenure",
    ]

    if any(term in title for term in exclude_terms):
        return False

    faculty_terms = [
        "assistant professor",
        "assistant/associate professor",
        "assistant or associate professor",
        "associate professor",
        "professor",
        "faculty position",
        "faculty positions",
        "faculty opening",
        "faculty openings",
        "tenure-track",
        "tenure track",
        "open rank",
        "research fellow",
    ]

    return any(term in title for term in faculty_terms)


def contains_phrase(text, phrase):
    """
    Match a phrase using word boundaries so that short keywords
    such as HRI do not accidentally match inside other words.
    """
    pattern = r"\b" + re.escape(phrase.lower()) + r"\b"
    return re.search(pattern, text.lower()) is not None


def score_detailed_job(job, config=None):
    """
    Score faculty jobs for relevance to HCI, Information Science,
    HRI, Design, Architecture, and related areas.
    """

    title = job.title.lower()
    organization = job.organization.lower()
    subjects = job.subject_areas.lower()
    description = job.description.lower()

    # ---------------------------------------------------------
    # Strong research-area phrases
    # ---------------------------------------------------------

    core_phrases = [
        "human-computer interaction",
        "human computer interaction",
        "human-centered computing",
        "human centered computing",
        "human-ai interaction",
        "human ai interaction",
        "human-robot interaction",
        "human robot interaction",
        "interaction design",
        "interactive systems",
        "user experience",
        "ubiquitous computing",
        "spatial computing",
        "embodied interaction",
        "social computing",
        "computer-supported cooperative work",
        "computer supported cooperative work",
    ]

    # ---------------------------------------------------------
    # Relevant disciplinary areas
    # ---------------------------------------------------------

    related_phrases = [
        "information science",
        "information studies",
        "human centered design",
        "human-centered design",
        "industrial design",
        "product design",
        "experience design",
        "interface design",
        "computational design",
        "architectural design",
        "environmental design",
        "digital design",
        "design technology",
        "mixed reality",
        "augmented reality",
        "virtual reality",
        "tangible interaction",
        "wearable computing",
    ]

    # ---------------------------------------------------------
    # Terms that are useful but too broad to establish relevance
    # by themselves
    # ---------------------------------------------------------

    supporting_phrases = [
        "robotics",
        "artificial intelligence",
        "machine learning",
        "computer science",
        "cognitive science",
        "visualization",
        "interactive",
    ]

    score = 0
    matches = []

    # Title is strongest evidence
    for phrase in core_phrases:
        if contains_phrase(title, phrase):
            score += 10
            matches.append(f"title: {phrase}")

    for phrase in related_phrases:
        if contains_phrase(title, phrase):
            score += 7
            matches.append(f"title: {phrase}")

    # Department / organization
    for phrase in core_phrases:
        if contains_phrase(organization, phrase):
            score += 8
            matches.append(f"department: {phrase}")

    for phrase in related_phrases:
        if contains_phrase(organization, phrase):
            score += 5
            matches.append(f"department: {phrase}")

    # Subject areas
    for phrase in core_phrases:
        if contains_phrase(subjects, phrase):
            score += 8
            matches.append(f"subject: {phrase}")

    for phrase in related_phrases:
        if contains_phrase(subjects, phrase):
            score += 5
            matches.append(f"subject: {phrase}")

    # Description provides weaker evidence
    for phrase in core_phrases:
        if contains_phrase(description, phrase):
            score += 4
            matches.append(f"description: {phrase}")

    for phrase in related_phrases:
        if contains_phrase(description, phrase):
            score += 2
            matches.append(f"description: {phrase}")

    # Supporting terms should never create a strong match alone
    supporting_matches = []

    combined = " ".join([
        title,
        organization,
        subjects,
        description,
    ])

    for phrase in supporting_phrases:
        if contains_phrase(combined, phrase):
            supporting_matches.append(phrase)

    # ---------------------------------------------------------
    # Explicit false-positive corrections
    # ---------------------------------------------------------

    false_positive_phrases = [
        "quantum information science",
        "quantum information",
        "bioinformatics",
        "medical informatics",
        "health informatics",
        "computer architecture",
        "experimental design",
        "research design",
        "study design",
    ]

    for phrase in false_positive_phrases:
        if contains_phrase(combined, phrase):
            score -= 2

    # ---------------------------------------------------------
    # Classification
    # ---------------------------------------------------------

    if score >= 8:
        level = "STRONG"

    elif score >= 4:
        level = "POSSIBLE"

    else:
        return None

    return {
        "level": level,
        "score": score,
        "matches": matches,
        "supporting": supporting_matches,
    }


def main():

    init_db()

    config = load_config()

    print("Searching AcademicJobsOnline...")

    jobs = fetch_jobs()

    print(f"\nScanned {len(jobs)} jobs.")

    faculty_jobs = [
        job for job in jobs
        if is_faculty_candidate(job)
    ]

    print(
        f"Found {len(faculty_jobs)} faculty candidates "
        f"before relevance filtering.\n"
    )

    matches = []

    for index, job in enumerate(faculty_jobs, start=1):

        print(
            f"Reading {index}/{len(faculty_jobs)}: "
            f"{job.title[:60]}"
        )

        try:
            fetch_job_details(job)

        except Exception as error:
            print(f"  Could not read job: {error}")
            continue

        if not is_job_open(job):
            continue

        result = score_detailed_job(
            job,
            config,
        )


        if result:

            is_new = save_job(
                job,
                result["level"],
                result["score"],
            )

            result["is_new"] = is_new

            matches.append(
                (
                    result,
                    job,
                )
            )

        # Be reasonably polite to the website
        time.sleep(0.15)

    strong_matches = [
        item
        for item in matches
        if item[0]["level"] == "STRONG"
    ]

    possible_matches = [
        item
        for item in matches
        if item[0]["level"] == "POSSIBLE"
    ]

    new_matches = [
    item
    for item in matches
    if item[0]["is_new"]
    ]

    print("\n" + "=" * 70)
    print("SEARCH COMPLETE")
    print("=" * 70)

    print(
        f"\nNew jobs since last run: "
        f"{len(new_matches)}"
    )

    print(
        f"\nStrong matches: {len(strong_matches)}"
    )

    for result, job in strong_matches:

        status = "NEW" if result["is_new"] else "SEEN"

        print("\n" + "-" * 70)
        print(
            f"[STRONG] [{status}] {job.title}"
        )
        print(f"Organization: {job.organization}")
        print(f"Subject areas: {job.subject_areas}")
        print(f"Deadline: {job.deadline}")

        print(f"Relevance score: {result['score']}")

        print(
            "Evidence:",
             ", ".join(result["matches"])
        )

        if result["supporting"]:
            print(
                "Supporting areas:",
                 ", ".join(result["supporting"])
            )

        print(f"URL: {job.url}")

    print(
        f"\n\nPossible matches: "
        f"{len(possible_matches)}"
    )

    for result, job in possible_matches:

        status = "NEW" if result["is_new"] else "SEEN"

        print("\n" + "-" * 70)
        print(
            f"[POSSIBLE] [{status}] {job.title}"
        )
        print(f"Organization: {job.organization}")
        print(f"Subject areas: {job.subject_areas}")
        print(f"Deadline: {job.deadline}")

        print(f"Relevance score: {result['score']}")

        print(
            "Evidence:",
            ", ".join(result["matches"])
        )

        if result["supporting"]:
            print(
             "Supporting areas:",
              ", ".join(result["supporting"])
             )

        print(f"URL: {job.url}")


if __name__ == "__main__":
    main()
