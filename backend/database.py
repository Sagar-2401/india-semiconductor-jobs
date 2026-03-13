"""Database operations for the semiconductor jobs platform."""
import sqlite3
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("DB_PATH", os.path.join(ROOT, "data", "semijobs.db"))


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    schema_path = os.path.join(ROOT, "database", "schema.sql")
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


def get_stats():
    conn = get_db()
    r = {
        "companies": conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        "jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "fresher_jobs": conn.execute("SELECT COUNT(*) FROM jobs WHERE fresher_suitable=1").fetchone()[0],
        "domains": conn.execute("SELECT COUNT(DISTINCT domain) FROM jobs WHERE domain IS NOT NULL").fetchone()[0],
    }
    conn.close()
    return r


def get_companies(search=None, domain=None, fresher_min=None, sort="best", limit=200, offset=0):
    conn = get_db()
    q = "SELECT * FROM companies WHERE 1=1"
    p = []
    if search:
        q += " AND (name LIKE ? OR description LIKE ? OR india_locations LIKE ?)"
        p += [f"%{search}%"] * 3
    if domain:
        q += " AND job_domains LIKE ?"
        p.append(f"%{domain}%")
    if fresher_min:
        q += " AND fresher_score >= ?"
        p.append(fresher_min)
    if sort == "best":
        q += " ORDER BY fresher_score DESC, fresher_salary_max DESC"
    elif sort == "salary":
        q += " ORDER BY fresher_salary_max DESC"
    else:
        q += " ORDER BY name"
    q += " LIMIT ? OFFSET ?"
    p += [limit, offset]
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_jobs(search=None, domain=None, fresher=None, salary_min=None,
             location=None, sort="recent", limit=50, offset=0):
    conn = get_db()
    q = "SELECT * FROM jobs WHERE 1=1"
    p = []
    if search:
        q += " AND (title LIKE ? OR company_name LIKE ? OR description LIKE ?)"
        p += [f"%{search}%"] * 3
    if domain:
        q += " AND domain = ?"
        p.append(domain)
    if fresher:
        q += " AND fresher_suitable = 1"
    if salary_min:
        q += " AND salary_max >= ?"
        p.append(salary_min)
    if location:
        q += " AND location LIKE ?"
        p.append(f"%{location}%")
    if sort == "recent":
        q += " ORDER BY posted_date DESC, created_at DESC"
    elif sort == "salary":
        q += " ORDER BY salary_max DESC"
    elif sort == "best":
        q += " ORDER BY fresher_suitable DESC, salary_max DESC"
    else:
        q += " ORDER BY created_at DESC"
    q += " LIMIT ? OFFSET ?"
    p += [limit, offset]
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_domains():
    conn = get_db()
    rows = conn.execute(
        "SELECT domain, COUNT(*) as count FROM jobs WHERE domain IS NOT NULL GROUP BY domain ORDER BY count DESC"
    ).fetchall()
    conn.close()
    return [{"domain": r[0], "count": r[1]} for r in rows]


def insert_job(data: dict):
    conn = get_db()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO jobs
            (company_name, title, location, url, source, description,
             posted_date, salary_min, salary_max, experience_min, experience_max,
             domain, skills, fresher_suitable, ai_classified)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("company_name", ""),
            data.get("title", ""),
            data.get("location"),
            data.get("url"),
            data.get("source"),
            data.get("description"),
            data.get("posted_date"),
            data.get("salary_min"),
            data.get("salary_max"),
            data.get("experience_min", 0),
            data.get("experience_max"),
            data.get("domain"),
            data.get("skills"),
            data.get("fresher_suitable", 0),
            data.get("ai_classified", 0),
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] Insert error: {e}")
        return False
    finally:
        conn.close()


def insert_company(data: dict):
    conn = get_db()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO companies
            (name, hq_country, india_locations, category, job_domains,
             fresher_salary_min, fresher_salary_max, fresher_score, description)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            data["name"], data.get("hq_country"), data.get("india_locations"),
            data.get("category"), data.get("job_domains"),
            data.get("fresher_salary_min"), data.get("fresher_salary_max"),
            data.get("fresher_score"), data.get("description"),
        ))
        conn.commit()
    except Exception as e:
        print(f"[DB] Company insert error: {e}")
    finally:
        conn.close()
