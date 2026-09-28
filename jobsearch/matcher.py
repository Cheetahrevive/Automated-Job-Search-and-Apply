"""Fit scoring: keyword include/exclude, salary band, sponsorship mentions,
remote/location filters. Returns (score 0-100, matched keywords, notes)."""
from __future__ import annotations

import re

from jobsearch.sources.base import Job

DEFAULT_WEIGHTS = {
    "title_include": 12.0,   # include-keyword hit in title
    "tag_include": 6.0,      # hit in tags
    "desc_include": 3.0,      # hit in description
    "exclude_penalty": 25.0,  # exclude-keyword hit anywhere
    "salary_bonus": 10.0,     # parsed salary meets band
    "salary_penalty": 15.0,   # parsed salary below minimum
    "remote_bonus": 5.0,
    "sponsorship_bonus": 8.0,
}

SPONSORSHIP_TERMS = [
    "h-1b", "h1b", "visa sponsorship", "sponsor visa",
    "work authorization", "will sponsor",
]


def parse_salary(text: str) -> tuple[float | None, float | None]:
    """Extract (min, max) annual USD from strings like '$100k-$150k',
    '€60,000', '120000'. Returns (None, None) when nothing parses."""
    if not text:
        return None, None
    clean = text.replace(",", "")
    nums = re.findall(r"\$?\s*(\d+(?:\.\d+)?)\s*([kK]?)", clean)
    values = []
    for num, k in nums:
        try:
            v = float(num)
        except ValueError:
            continue
        if k.lower() == "k":
            v *= 1000
        elif v < 1000 and v > 0:
            v *= 1000  # bare "120" almost surely means $120k in job ads
        values.append(v)
    if not values:
        return None, None
    lo, hi = min(values), max(values)
    return lo, hi


def mentions_sponsorship(text: str) -> bool:
    low = text.lower()
    return any(term in low for term in SPONSORSHIP_TERMS)


def score_job(job: Job, config: dict) -> tuple[float, list[str], list[str]]:
    """Score a job 0..100 against config. Returns (score, matched, notes)."""
    weights = {**DEFAULT_WEIGHTS, **config.get("weights", {})}
    include = [k.lower() for k in config.get("include_keywords", [])]
    exclude = [k.lower() for k in config.get("exclude_keywords", [])]

    title = (job.title or "").lower()
    desc = (job.description or "").lower()
    tags = " ".join(job.tags or []).lower()
    everywhere = f"{title} {desc} {tags}"

    matched: list[str] = []
    notes: list[str] = []
    score = 40.0  # base score; every job starts neutral

    for kw in include:
        if kw in title:
            score += weights["title_include"]
            matched.append(f"title:{kw}")
        elif kw in tags:
            score += weights["tag_include"]
            matched.append(f"tag:{kw}")
        elif kw in desc:
            score += weights["desc_include"]
            matched.append(f"desc:{kw}")

    for kw in exclude:
        if kw in everywhere:
            score -= weights["exclude_penalty"]
            notes.append(f"excluded by keyword '{kw}'")

    # Salary band
    lo, hi = parse_salary(job.salary_raw or "")
    salary_min = config.get("salary_min")
    salary_max = config.get("salary_max")
    if lo is not None:
        if salary_min and hi < salary_min:
            score -= weights["salary_penalty"]
            notes.append(f"salary below minimum ({job.salary_raw})")
        elif (not salary_min or lo >= salary_min) and (
            not salary_max or lo <= salary_max
        ):
            score += weights["salary_bonus"]
            notes.append(f"salary in band ({job.salary_raw})")

    # Remote / location
    remote_only = config.get("remote_only", False)
    if remote_only and not job.remote:
        score -= 50.0
        notes.append("not remote (remote_only set)")
    elif job.remote:
        score += weights["remote_bonus"]

    # Sponsorship
    if config.get("prefer_sponsorship_mentions"):
        if mentions_sponsorship(job.description or ""):
            score += weights["sponsorship_bonus"]
            notes.append("mentions sponsorship")
        else:
            notes.append("no sponsorship mention found")

    score = max(0.0, min(100.0, score))
    return round(score, 1), matched, notes
