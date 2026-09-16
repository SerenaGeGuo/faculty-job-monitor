import sqlite3
from datetime import datetime


DB_PATH = "jobs.db"


def init_db():
    """
    Create the jobs database if it does not already exist, and add
    any columns introduced after the table was first created.
    """

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            organization TEXT,
            source TEXT,
            subject_areas TEXT,
            position_type TEXT,
            deadline TEXT,
            relevance_level TEXT,
            relevance_score INTEGER,
            first_seen TEXT,
            last_seen TEXT
        )
        """
    )

    cursor.execute("PRAGMA table_info(jobs)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "description" not in existing_columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN description TEXT")

    conn.commit()
    conn.close()


def save_job(job, relevance_level, relevance_score):
    """
    Save a relevant job.

    Returns True if this is the first time the job has been seen.
    Returns False if it already exists.
    """

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM jobs WHERE url = ?",
        (job.url,),
    )

    existing_job = cursor.fetchone()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    if existing_job:

        cursor.execute(
            """
            UPDATE jobs
            SET
                title = ?,
                organization = ?,
                source = ?,
                subject_areas = ?,
                position_type = ?,
                deadline = ?,
                relevance_level = ?,
                relevance_score = ?,
                description = ?,
                last_seen = ?
            WHERE url = ?
            """,
            (
                job.title,
                job.organization,
                job.source,
                job.subject_areas,
                job.position_type,
                job.deadline,
                relevance_level,
                relevance_score,
                job.description,
                now,
                job.url,
            ),
        )

        is_new = False

    else:

        cursor.execute(
            """
            INSERT INTO jobs (
                url,
                title,
                organization,
                source,
                subject_areas,
                position_type,
                deadline,
                relevance_level,
                relevance_score,
                description,
                first_seen,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.url,
                job.title,
                job.organization,
                job.source,
                job.subject_areas,
                job.position_type,
                job.deadline,
                relevance_level,
                relevance_score,
                job.description,
                now,
                now,
            ),
        )

        is_new = True

    conn.commit()
    conn.close()

    return is_new


def get_all_jobs():
    """
    Return every job ever saved (i.e. every posting that has matched
    CORE/BROAD/ADJACENT relevance at some point), ordered by
    relevance level then most-recently-first-seen. Used to remind
    the user what was already sent in past digests, and to build the
    full Excel export.
    """

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT url, title, organization, source, deadline,
               relevance_level, relevance_score, first_seen,
               description
        FROM jobs
        ORDER BY
            CASE relevance_level
                WHEN 'CORE' THEN 0
                WHEN 'BROAD' THEN 1
                WHEN 'ADJACENT' THEN 2
                ELSE 3
            END,
            first_seen DESC
        """
    )

    rows = cursor.fetchall()

    conn.close()

    return [
        {
            "url": row[0],
            "title": row[1],
            "organization": row[2],
            "source": row[3],
            "deadline": row[4],
            "relevance_level": row[5],
            "relevance_score": row[6],
            "first_seen": row[7],
            "description": row[8],
        }
        for row in rows
    ]
