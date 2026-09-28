"""Tests for the SQLite store (dedupe, lifecycle, filters)."""
import pytest

from jobsearch.sources.base import Job
from jobsearch.store import VALID_STATUSES, Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _job(source="remotive", external_id="1", title="QA Engineer", score=75.0):
    return Job(source=source, external_id=external_id, title=title,
               company="Acme", fit_score=score)


def test_upsert_inserts_and_dedupes(store):
    inserted, updated = store.upsert_jobs([_job(), _job(title="Other")])
    assert (inserted, updated) == (1, 1)  # same (source, external_id): 1 insert + 1 update
    # refresh of score on re-upsert
    store.upsert_jobs([_job(score=90.0)])
    assert store.get(1)["fit_score"] == 90.0


def test_dedupe_across_sources(store):
    store.upsert_jobs([_job(source="remotive", external_id="x"),
                       _job(source="arbeitnow", external_id="x")])
    assert len(store.list()) == 2


def test_status_lifecycle(store):
    store.upsert_jobs([_job()])
    assert store.set_status(1, "saved")
    assert store.get(1)["status"] == "saved"
    assert store.list(status="saved")
    assert not store.list(status="applied")
    with pytest.raises(ValueError):
        store.set_status(1, "bogus")


def test_list_filters(store):
    store.upsert_jobs([_job(external_id="a", score=90.0),
                       _job(external_id="b", score=20.0)])
    assert len(store.list(min_score=50)) == 1
    assert len(store.list()) == 2


def test_stats(store):
    store.upsert_jobs([_job(external_id="a", score=80.0),
                       _job(external_id="b", score=60.0)])
    store.set_status(1, "reviewed")
    s = store.stats()
    assert s["total"] == 2
    assert s["by_status"] == {"new": 1, "reviewed": 1}
    assert s["by_source"] == {"remotive": 2}


def test_get_missing(store):
    assert store.get(999) is None
    assert not store.set_status(999, "saved")
