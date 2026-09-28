"""Tests for source adapters (HTTP stubbed via monkeypatch)."""
import io
import json

import pytest

from jobsearch.sources.adzuna import AdzunaSource
from jobsearch.sources.arbeitnow import ArbeitnowSource
from jobsearch.sources.remotive import RemotiveSource


def _stub_urlopen(monkeypatch, payload):
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(payload).encode()
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=30: FakeResp()
    )


REMOTIVE_PAYLOAD = {"jobs": [{
    "id": 42, "title": "QA Automation Engineer", "company_name": "Acme",
    "candidate_required_location": "Worldwide", "url": "https://example.com/j/42",
    "description": "<p>Playwright and API testing</p>", "salary": "$120k-$150k",
    "publication_date": "2026-09-20", "tags": ["qa", "playwright"],
}]}

ARBEITNOW_PAYLOAD = {"data": [{
    "slug": "abc123", "title": "QA Engineer", "company_name": "Beta",
    "location": "Berlin", "remote": True, "url": "https://example.com/j/abc",
    "description": "Selenium testing", "created_at": "2026-09-21",
    "tags": ["qa"],
}]}


def test_remotive_fetch(monkeypatch):
    _stub_urlopen(monkeypatch, REMOTIVE_PAYLOAD)
    jobs = RemotiveSource().fetch("qa", limit=10)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.external_id == "42" and j.company == "Acme" and j.remote is True
    assert "Playwright" in j.description and "<p>" not in j.description


def test_arbeitnow_fetch_and_query_filter(monkeypatch):
    _stub_urlopen(monkeypatch, ARBEITNOW_PAYLOAD)
    jobs = ArbeitnowSource().fetch("qa", limit=10)
    assert len(jobs) == 1 and jobs[0].external_id == "abc123"
    # query that matches nothing -> empty
    assert ArbeitnowSource().fetch("zookeeper", limit=10) == []


def test_adzuna_degrades_without_keys(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    src = AdzunaSource()
    ok, reason = src.available()
    assert ok is False and "ADZUNA_APP" in reason
    with pytest.raises(RuntimeError):
        src.fetch("qa")
