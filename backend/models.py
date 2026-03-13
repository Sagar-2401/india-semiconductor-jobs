from pydantic import BaseModel
from typing import Optional, List


class Company(BaseModel):
    id: int
    name: str
    hq_country: Optional[str] = None
    india_locations: Optional[str] = None
    category: Optional[str] = None
    job_domains: Optional[str] = None
    fresher_salary_min: Optional[int] = None
    fresher_salary_max: Optional[int] = None
    fresher_score: Optional[int] = None
    description: Optional[str] = None


class Job(BaseModel):
    id: int
    company_name: str
    title: str
    location: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    posted_date: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    experience_min: Optional[int] = 0
    experience_max: Optional[int] = None
    domain: Optional[str] = None
    skills: Optional[str] = None
    fresher_suitable: bool = False


class ClassifyRequest(BaseModel):
    title: str
    description: str


class ClassifyResult(BaseModel):
    domain: str
    skills: List[str]
    experience_estimate: str
    fresher_suitable: bool
