"""Tests for the fit-scoring matcher."""
from jobsearch.matcher import mentions_sponsorship, parse_salary, score_job
from jobsearch.sources.base import Job


def _job(**kw):
    base = dict(
        source="test", external_id="1", title="QA Automation Engineer",
        company="Acme", description="", salary_raw="", tags=[],
    )
    base.update(kw)
    return Job(**base)


def _config(**kw):
    cfg = dict(
        include_keywords=["qa", "playwright", "selenium"],
        exclude_keywords=["manual only"],
        salary_min=100000,
        salary_max=None,
        remote_only=False,
        prefer_sponsorship_mentions=True,
        weights={},
    )
    cfg.update(kw)
    return cfg


def test_include_keyword_in_title_scores_higher():
    good = _job(title="QA Automation Engineer (Playwright)")
    bad = _job(title="Backend Developer")
    assert score_job(good, _config())[0] > score_job(bad, _config())[0]


def test_exclude_keyword_penalizes():
    cfg = _config()
    excluded = _job(title="QA Engineer", description="manual only role")
    plain = _job(title="QA Engineer")
    assert score_job(excluded, cfg)[0] < score_job(plain, cfg)[0]


def test_salary_band():
    cfg = _config()
    in_band = _job(salary_raw="$120k-$150k")
    below = _job(salary_raw="$60k-$70k")
    assert score_job(in_band, cfg)[0] > score_job(below, cfg)[0]


def test_remote_only_penalizes_onsite():
    cfg = _config(remote_only=True)
    onsite = _job(remote=False)
    remote = _job(remote=True)
    assert score_job(remote, cfg)[0] > score_job(onsite, cfg)[0]


def test_sponsorship_mention_bonus():
    cfg = _config()
    sponsored = _job(description="we provide H-1B visa sponsorship")
    other = _job(description="great benefits")
    s1, _, notes1 = score_job(sponsored, cfg)
    s2, _, _ = score_job(other, cfg)
    assert s1 > s2
    assert any("sponsorship" in n for n in notes1)


def test_score_is_clamped():
    cfg = _config(include_keywords=["qa"] * 50)
    s, _, _ = score_job(_job(title="qa"), cfg)
    assert 0 <= s <= 100


def test_parse_salary_variants():
    assert parse_salary("$100k-$150k") == (100000.0, 150000.0)
    assert parse_salary("€60,000") == (60000.0, 60000.0)
    assert parse_salary("not listed") == (None, None)
    assert parse_salary("") == (None, None)


def test_mentions_sponsorship():
    assert mentions_sponsorship("H1B sponsorship available")
    assert not mentions_sponsorship("unlimited PTO")
