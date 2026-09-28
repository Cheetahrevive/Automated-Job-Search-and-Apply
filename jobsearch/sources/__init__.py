"""Job-source adapter registry."""
from jobsearch.sources.adzuna import AdzunaSource
from jobsearch.sources.arbeitnow import ArbeitnowSource
from jobsearch.sources.base import Job, JobSource
from jobsearch.sources.remotive import RemotiveSource

__all__ = ["Job", "JobSource", "SOURCES"]


def _all_sources() -> dict[str, JobSource]:
    return {
        "remotive": RemotiveSource(),
        "arbeitnow": ArbeitnowSource(),
        "adzuna": AdzunaSource(),
    }


SOURCES: dict[str, JobSource] = _all_sources()
