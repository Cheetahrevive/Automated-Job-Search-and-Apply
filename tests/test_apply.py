"""Tests for the approval-gated apply flow."""
import os

import pytest

from jobsearch import apply as apply_mod
from jobsearch.store import Store


@pytest.fixture
def job_and_store(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    from jobsearch.sources.base import Job
    store.upsert_jobs([Job(source="remotive", external_id="1",
                           title="QA Engineer", company="Acme",
                           url="https://example.com/j/1", fit_score=80.0)])
    job = store.get(1)
    yield job, store, tmp_path
    store.close()


def _config():
    return {"name": "Test User", "email": "t@example.com",
            "resume_path": "/tmp/resume.pdf"}


def test_dry_run_prints_and_changes_nothing(job_and_store, capsys):
    job, store, _ = job_and_store
    rc = apply_mod.cmd_apply(job, _config(), store, confirm=None,
                             out_dir="unused")
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out and "https://example.com/j/1" in out
    assert store.get(1)["status"] == "new"  # untouched
    assert not os.path.exists("unused")  # no package written


def test_export_requires_matching_confirmation(job_and_store, tmp_path):
    job, store, _ = job_and_store
    out_dir = str(tmp_path / "apps")
    # wrong token -> rejected, nothing changes
    rc = apply_mod.cmd_apply(job, _config(), store, confirm="999", out_dir=out_dir)
    assert rc == 2
    assert store.get(1)["status"] == "new"
    # correct token (the job id) -> package written, status -> applied
    rc = apply_mod.cmd_apply(job, _config(), store, confirm="1", out_dir=out_dir)
    assert rc == 0
    files = os.listdir(out_dir)
    assert len(files) == 1
    text = open(os.path.join(out_dir, files[0])).read()
    assert "NOT submitted" in text and "Acme" in text
    assert store.get(1)["status"] == "applied"


def test_ask_confirmation_matching():
    assert apply_mod.ask_confirmation(7, "7") is True
    assert apply_mod.ask_confirmation(7, "yes") is False
    assert apply_mod.ask_confirmation(7, "8") is False
