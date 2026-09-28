"""Remotive API adapter — free, keyless JSON API.
https://remotive.com/api/remote-jobs
"""
from __future__ import annotations

import json
import urllib.request

from jobsearch.sources.base import Job, JobSource

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveSource(JobSource):
    name = "remotive"

    def fetch(self, query: str, limit: int = 50) -> list[Job]:
        params = f"?search={urllib.request.quote(query)}&limit={min(limit, 200)}"
        req = urllib.request.Request(API_URL + params, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
        jobs: list[Job] = []
        for item in payload.get("jobs", [])[:limit]:
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("title", "") or "",
                    company=item.get("company_name", "") or "",
                    location=item.get("candidate_required_location", "") or "",
                    remote=True,
                    url=item.get("url", "") or "",
                    description=_strip_html(item.get("description", "") or ""),
                    salary_raw=item.get("salary", "") or "",
                    posted_at=item.get("publication_date", "") or "",
                    tags=list(item.get("tags", []) or []),
                )
            )
        return jobs


_HEADERS = {"User-Agent": "jobsearch-cli/0.1 (+github.com/Cheetahrevive)"}


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:4000]
