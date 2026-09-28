"""Adzuna API adapter — requires app_id/app_key.

Reads credentials from the ``ADZUNA_APP_ID`` / ``ADZUNA_APP_KEY``
environment variables (or ``adzuna`` section of the config file).
Degrades gracefully when keys are absent: ``available()`` reports
False and the CLI skips it with a warning.
https://developer.adzuna.com/
"""
from __future__ import annotations

import json
import os
import urllib.request

from jobsearch.sources.base import Job, JobSource

API_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


class AdzunaSource(JobSource):
    name = "adzuna"

    def __init__(self, app_id: str | None = None, app_key: str | None = None,
                 country: str = "us"):
        self.app_id = app_id or os.environ.get("ADZUNA_APP_ID", "")
        self.app_key = app_key or os.environ.get("ADZUNA_APP_KEY", "")
        self.country = country

    def available(self) -> tuple[bool, str]:
        if not (self.app_id and self.app_key):
            return (
                False,
                "ADZUNA_APP_ID / ADZUNA_APP_KEY not set — skipping (see README)",
            )
        return True, ""

    def fetch(self, query: str, limit: int = 50) -> list[Job]:
        ok, reason = self.available()
        if not ok:
            raise RuntimeError(reason)
        url = API_URL.format(country=self.country) + (
            f"?app_id={urllib.request.quote(self.app_id)}"
            f"&app_key={urllib.request.quote(self.app_key)}"
            f"&results_per_page={min(limit, 50)}"
            f"&what={urllib.request.quote(query)}"
            "&content-type=application/json"
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "jobsearch-cli/0.1 (+github.com/Cheetahrevive)"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
        jobs: list[Job] = []
        for item in payload.get("results", [])[:limit]:
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("title", "") or "",
                    company=(item.get("company", {}) or {}).get("display_name", "") or "",
                    location=(item.get("location", {}) or {}).get("display_name", "") or "",
                    remote="remote" in (item.get("title", "") or "").lower(),
                    url=item.get("redirect_url", "") or "",
                    description=item.get("description", "") or "",
                    salary_raw=_salary(item),
                    posted_at=item.get("created", "") or "",
                    tags=[item.get("category", {}).get("label", "") or ""],
                )
            )
        return jobs


def _salary(item: dict) -> str:
    lo, hi = item.get("salary_min"), item.get("salary_max")
    if lo and hi:
        return f"${int(lo)}-${int(hi)}"
    if lo:
        return f"${int(lo)}+"
    return ""
