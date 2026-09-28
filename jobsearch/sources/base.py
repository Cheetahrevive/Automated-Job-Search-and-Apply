"""Common job-source interface and the Job record."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Job:
    source: str          # e.g. "remotive", "arbeitnow", "adzuna"
    external_id: str     # id assigned by the source
    title: str
    company: str
    location: str = ""
    remote: bool = False
    url: str = ""
    description: str = ""
    salary_raw: str = ""
    posted_at: str = ""
    tags: list = field(default_factory=list)
    fit_score: float = 0.0


class JobSource(ABC):
    """Pluggable job-source adapter interface."""

    name: str = "base"

    @abstractmethod
    def fetch(self, query: str, limit: int = 50) -> list[Job]:
        """Fetch up to ``limit`` jobs matching ``query``. Must never raise
        for missing credentials — degrade gracefully instead."""

    def available(self) -> tuple[bool, str]:
        """Return (ok, reason). False + reason when the source can't run
        (e.g. missing API keys); the CLI will skip it with a warning."""
        return True, ""
