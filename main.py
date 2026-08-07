import yaml
import time
import re
from datetime import datetime

from job_monitor.scrapers.academic_jobs_online import (
    fetch_jobs,
    fetch_job_details,
)

#from job_monitor.scrapers.higher_ed_jobs import (
#    test_access,
#)

from job_monitor.scrapers.ischools import (
    fetch_jobs as fetch_ischools_jobs,
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

def is_senior_only(job):
    """
    Return True when a posting is clearly intended only for
    senior faculty and does not include an entry-level rank.
    """

    title = job.title.lower()

    # If the position explicitly allows an assistant-professor
    # or open-rank applicant, keep it.
    junior_or_open_signals = [
        "assistant professor",
        "assistant/associate professor",
        "assistant or associate professor",
        "assistant professorship",
        "assistant professorships",
        "open rank",
        "open-rank",
        "tenure-track faculty",
        "tenure track faculty",
        "faculty position",
        "faculty positions",
        "research fellow",
    ]

    if any(
        term in title
        for term in junior_or_open_signals
    ):
        return False

    senior_only_terms = [
        "full professor",
        "associate professor",
        "professor and head",
        "professor and chair",
        "department chair",
        "department head",
        "chair professor",
        "endowed professor",
        "endowed professorship",
        "tenured professor",
        "associate/full professor",
        "associate or full professor",
        "full professors",
    ]

    return any(
        term in title
        for term in senior_only_terms
    )

def contains_phrase(text, phrase):
    """
    Match a phrase using word boundaries so that short keywords
    such as HRI do not accidentally match inside other words.
    """
    pattern = r"\b" + re.escape(phrase.lower()) + r"\b"
    return re.search(pattern, text.lower()) is not None


def score_detailed_job(job, config=None):
    """
    Classify a faculty job into:

    CORE:
        Explicit HCI, HRI, Information Science, Human-AI,
        Interaction Design, Human-Centered Computing, etc.

    BROAD:
        General CS, Information, Design, Architecture, or
        related departments where an HCI/design researcher
        could reasonably apply.

    ADJACENT:
        Robotics, XR, visualization, AI, cognitive science,
        digital media, etc.
    """

    title = job.title.lower()
    organization = job.organization.lower()
    subjects = job.subject_areas.lower()
    description = job.description.lower()

    # ---------------------------------------------------------
    # CORE: direct intellectual fit
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
        "interface design",
        "social computing",
        "ubiquitous computing",
        "embodied interaction",
        "tangible interaction",
        "computer-supported cooperative work",
        "computer supported cooperative work",
        "spatial computing",
        "human centered design",
        "human-centered design",
    ]

    # ---------------------------------------------------------
    # BROAD: departments / disciplines worth applying to
    # ---------------------------------------------------------

    broad_phrases = [
        "computer science",
        "information science",
        "information studies",
        "informatics",
        "industrial design",
        "product design",
        "computational design",
        "architectural design",
        "architecture",
        "environmental design",
        "design technology",
        "digital design",
        "interaction media",
        "computational media",
    ]

    # ---------------------------------------------------------
    # ADJACENT: potentially relevant research neighborhoods
    # ---------------------------------------------------------

    adjacent_phrases = [
        "robotics",
        "augmented reality",
        "virtual reality",
        "mixed reality",
        "extended reality",
        "visualization",
        "computer graphics",
        "cognitive science",
        "artificial intelligence",
        "digital media",
        "interactive media",
        "wearable computing",
        "internet of things",
    ]

    # ---------------------------------------------------------
    # 1. Look for CORE evidence
    # ---------------------------------------------------------

    core_evidence = []
    core_score = 0

    # Title
    for phrase in core_phrases:
        if contains_phrase(title, phrase):
            core_score += 10
            core_evidence.append(
                f"title: {phrase}"
            )

    # Organization / department
    for phrase in core_phrases:
        if contains_phrase(organization, phrase):
            core_score += 8
            core_evidence.append(
                f"department: {phrase}"
            )

    # Subject areas
    for phrase in core_phrases:
        if contains_phrase(subjects, phrase):
            core_score += 8
            core_evidence.append(
                f"subject: {phrase}"
            )

    # Description is weaker evidence
    for phrase in core_phrases:
        if contains_phrase(description, phrase):
            core_score += 3
            core_evidence.append(
                f"description: {phrase}"
            )

    core_threshold = (
        3
        if job.source == "iSchools"
        else 6
    )

    if core_score >= core_threshold:
        return {
            "level": "CORE",
            "score": core_score,
            "matches": core_evidence,
            "supporting": [],
        }

    # ---------------------------------------------------------
    # 2. Look for BROAD disciplinary fit
    #
    # IMPORTANT:
    # We intentionally do NOT use the description here.
    # Otherwise phrases such as "research design" or
    # "computer architecture" create many false positives.
    # ---------------------------------------------------------

    broad_evidence = []
    broad_score = 0

    broad_fields = [
        ("title", title, 7),
        ("department", organization, 6),
        ("subject", subjects, 5),
    ]

    for field_name, field_text, weight in broad_fields:

        for phrase in broad_phrases:

            if not contains_phrase(
                field_text,
                phrase,
            ):
                continue

            # Prevent Quantum Information Science
            # from becoming an Information Science match.
            if (
                phrase == "information science"
                and contains_phrase(
                    field_text,
                    "quantum information science",
                )
            ):
                continue

            broad_score += weight

            broad_evidence.append(
                f"{field_name}: {phrase}"
            )

    if broad_score >= 5:
        return {
            "level": "BROAD",
            "score": broad_score,
            "matches": broad_evidence,
            "supporting": [],
        }

    # ---------------------------------------------------------
    # 3. Look for ADJACENT areas
    # ---------------------------------------------------------

    adjacent_evidence = []
    adjacent_score = 0

    adjacent_fields = [
        ("title", title, 5),
        ("department", organization, 4),
        ("subject", subjects, 4),
        ("description", description, 1),
    ]

    for field_name, field_text, weight in adjacent_fields:

        for phrase in adjacent_phrases:

            if contains_phrase(
                field_text,
                phrase,
            ):
                adjacent_score += weight

                adjacent_evidence.append(
                    f"{field_name}: {phrase}"
                )

    if adjacent_score >= 4:
        return {
            "level": "ADJACENT",
            "score": adjacent_score,
            "matches": adjacent_evidence,
            "supporting": [],
        }

    return None


def main():

    init_db()

    config = load_config()

    print("Searching AcademicJobsOnline...")

    jobs = fetch_jobs()

    print(f"\nScanned {len(jobs)} jobs.")

    faculty_jobs = [
        job
        for job in jobs
        if is_faculty_candidate(job)
        and not is_senior_only(job)
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

    # =========================================================
    # iSchools
    # =========================================================

    print("\n" + "=" * 70)
    print("Searching iSchools Jobs...")
    print("=" * 70)

    ischools_jobs = fetch_ischools_jobs(
        max_pages=5,
    )

    print(
        f"\nScanned {len(ischools_jobs)} "
        f"iSchools jobs."
    )

    ischools_faculty_jobs = [
        job
        for job in ischools_jobs
        if is_faculty_candidate(job)
        and not is_senior_only(job)
    ]

    print(
        f"Found {len(ischools_faculty_jobs)} "
        f"iSchools faculty candidates "
        f"before relevance filtering.\n"
    )

    for index, job in enumerate(
        ischools_faculty_jobs,
        start=1,
    ):

        print(
            f"Evaluating iSchools "
            f"{index}/{len(ischools_faculty_jobs)}: "
            f"{job.title[:60]}"
        )

        # Details are already loaded by
        # fetch_ischools_jobs(), so unlike AJO
        # we do not call fetch_job_details() here.

        if not is_job_open(job):
            print("  Skipping: deadline passed")
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

    core_matches = [
    item
    for item in matches
    if item[0]["level"] == "CORE"
    ]

    broad_matches = [
        item
        for item in matches
        if item[0]["level"] == "BROAD"
    ]

    adjacent_matches = [
        item
        for item in matches
        if item[0]["level"] == "ADJACENT"
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
        f"\nCORE matches: {len(core_matches)}"
    )


    for result, job in core_matches:

        status = (
            "NEW"
            if result["is_new"]
            else "SEEN"
        )

        print("\n" + "-" * 70)

        print(
            f"[CORE] [{status}] {job.title}"
        )

        print(
            f"Organization: "
            f"{job.organization}"
        )

        print(
            f"Subject areas: "
            f"{job.subject_areas}"
        )

        print(
            f"Deadline: "
            f"{job.deadline}"
        )

        print(
            f"Relevance score: "
            f"{result['score']}"
        )

        print(
            "Evidence:",
            ", ".join(result["matches"])
        )

        print(
            f"URL: {job.url}"
        )


    print(
        f"\n\nBROAD matches: "
        f"{len(broad_matches)}"
    )

    for result, job in broad_matches:

        status = (
            "NEW"
            if result["is_new"]
            else "SEEN"
        )

        print("\n" + "-" * 70)

        print(
            f"[BROAD] [{status}] {job.title}"
        )

        print(
            f"Organization: "
            f"{job.organization}"
        )

        print(
            f"Subject areas: "
            f"{job.subject_areas}"
        )

        print(
            f"Deadline: "
            f"{job.deadline}"
        )

        print(
            f"Relevance score: "
            f"{result['score']}"
        )

        print(
            "Evidence:",
            ", ".join(result["matches"])
        )

        print(
            f"URL: {job.url}"
        )


    print(
        f"\n\nADJACENT matches: "
        f"{len(adjacent_matches)}"
    )

    for result, job in adjacent_matches:

        status = (
            "NEW"
            if result["is_new"]
            else "SEEN"
        )

        print("\n" + "-" * 70)

        print(
            f"[ADJACENT] [{status}] "
            f"{job.title}"
        )

        print(
            f"Organization: "
            f"{job.organization}"
        )

        print(
            f"Subject areas: "
            f"{job.subject_areas}"
        )

        print(
            f"Deadline: "
            f"{job.deadline}"
        )

        print(
            f"Relevance score: "
            f"{result['score']}"
        )

        print(
            "Evidence:",
            ", ".join(result["matches"])
        )

        print(
            f"URL: {job.url}"
        )


if __name__ == "__main__":
    main()