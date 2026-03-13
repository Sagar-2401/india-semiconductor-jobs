-- India Semiconductor Jobs Platform - Database Schema

CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  hq_country TEXT,
  india_locations TEXT,
  category TEXT,
  job_domains TEXT,          -- comma-separated domain codes
  fresher_salary_min INTEGER,
  fresher_salary_max INTEGER,
  fresher_score INTEGER CHECK (fresher_score BETWEEN 1 AND 5),
  description TEXT,
  career_url TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT NOT NULL,
  title TEXT NOT NULL,
  location TEXT,
  url TEXT UNIQUE,
  source TEXT,               -- 'jsearch','adzuna','career_page','manual'
  description TEXT,
  posted_date TEXT,
  salary_min INTEGER,
  salary_max INTEGER,
  experience_min INTEGER DEFAULT 0,
  experience_max INTEGER,
  domain TEXT,               -- VLSI, FPGA, Embedded, etc.
  skills TEXT,               -- comma-separated
  fresher_suitable INTEGER DEFAULT 0,
  ai_classified INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_domain ON jobs(domain);
CREATE INDEX IF NOT EXISTS idx_jobs_fresher ON jobs(fresher_suitable);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_name);
CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date DESC);
CREATE INDEX IF NOT EXISTS idx_companies_score ON companies(fresher_score DESC);
