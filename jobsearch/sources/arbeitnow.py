"""Arbeitnow API adapter — free, keyless JSON API.
https://arbeitnow.com/api/job-board-api
"""
from __future__ import annotations

import json
import urllib.request

from jobsearch.sources.base import Job, JobSource

API_URL = "https://arbeitnow.com/api/job-board-api"


class ArbeitnowSource(JobSource):
    name = "arbeitnow"

    def fetch(self, query: str, limit: int = 50) -> list[Job]:
        req = urllib.request.Request(
            API_URL, headers={"User-Agent": "jobsearch-cli/0.1 (+github.com/Cheetahrevive)"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
        query_terms = [t.lower() for t in query.split()]
        jobs: list[Job] = []
        data = payload.get("data", []) if isinstance(payload, dict) else []
        for item in data:
            haystack = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("company_name", "")),
                    str(item.get("description", "")),
                    " ".join(item.get("tags", []) or []),
                ]
            ).lower()
            if query_terms and not any(t in haystack for t in query_terms):
                continue
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("slug", "")),
                    title=item.get("title", "") or "",
                    company=item.get("company_name", "") or "",
                    location=item.get("location", "") or "",
                    remote=bool(item.get("remote")),
                    url=item.get("url", "") or "",
                    description=(item.get("description", "") or "")[:4000],
                    salary_raw="",
                    posted_at=item.get("created_at", "") or "",
                    tags=list(item.get("tags", []) or []),
                )
            )
            if len(jobs) >= limit:
                break
        return jobs
