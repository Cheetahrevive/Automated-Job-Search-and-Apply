# Automated Job Search & Apply

A Python CLI that searches job boards, scores fit against your profile, and tracks
applications in a local SQLite database — **without ever submitting an application
automatically**.

## ⚠️ Approval-gated apply — read this first

This tool **cannot and will never submit a job application on your behalf**.
There is no HTTP POST, no form-fill, no auto-submit anywhere in the codebase —
by design, not by accident.

What `apply` actually does:

| Mode | Command | Effect |
|------|---------|--------|
| **Dry-run (default)** | `python -m jobsearch.cli apply 42` | Prints a summary of the job and the apply URL so you can apply manually in your own browser. Changes nothing. |
| **Confirmed export** | `python -m jobsearch.cli apply 42 --confirm 42` | After you **type the job id as explicit per-job confirmation**, writes a prepared application package (cover-note draft + job details + resume path reference) to `./applications/` and marks the job `applied` in the local database. Still submits nothing. |

Without a matching `--confirm <job-id>` the command refuses to export anything.
The confirmation is per job, every time — there is no "auto-apply everything"
flag and there never will be.

## How it works

```
search  →  score  →  store (SQLite)  →  review  →  apply (manual, gated)
```

- **Sources** (pluggable, see `jobsearch/sources/`): Remotive and Arbeitnow
  (free, keyless JSON APIs) ship working out of the box. Adzuna ships too but
  needs `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` env vars (or the `adzuna` config
  section); it degrades gracefully to a warning when keys are absent.
- **Fit scoring** (`matcher.py`): include/exclude keywords (title hits weigh
  most), salary band parsing (`$120k–$150k`, `€60,000`), remote-only filter,
  and H-1B/sponsorship-mention detection. Scores are 0–100 with notes stored
  per job explaining the score.
- **Store** (`store.py`): SQLite, deduped by `(source, external_id)`.
  Status lifecycle: `new → reviewed | saved | skipped | applied`.

## Install & run (verified)

Requires Python 3.10+. The runtime is stdlib-only; `pytest` is needed for tests.

```bash
git clone https://github.com/Cheetahrevive/Automated-Job-Search-and-Apply.git
cd Automated-Job-Search-and-Apply
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Copy and edit the example config (QA/SDET-tuned defaults)
cp config.example.json config.json
#    edit: name, email, resume_path, query, include/exclude keywords,
#    salary band, remote_only, db_path

# 2. Search, score, store
python -m jobsearch.cli -c config.json search

# 3. Review matches
python -m jobsearch.cli -c config.json list --min-score 60
python -m jobsearch.cli -c config.json show 3
python -m jobsearch.cli -c config.json stats

# 4. Triage
python -m jobsearch.cli -c config.json status 3 saved

# 5. Apply helper (dry-run first; see approval-gate section above)
python -m jobsearch.cli -c config.json apply 3
python -m jobsearch.cli -c config.json apply 3 --confirm 3 --out-dir ./applications
```

All of the above commands were executed and verified during development
(search returned 36 live jobs from Remotive + Arbeitnow, scored, stored,
listed, and the apply dry-run/confirm flow behaved as documented).

## Config reference (`config.example.json`)

| Key | Meaning |
|-----|---------|
| `query` | search query sent to sources |
| `sources` | subset of `["remotive", "arbeitnow", "adzuna"]` |
| `limit_per_source` | max jobs fetched per source |
| `include_keywords` / `exclude_keywords` | fit-scoring keyword lists |
| `salary_min` / `salary_max` | annual USD band filter |
| `remote_only` | penalize non-remote jobs when true |
| `prefer_sponsorship_mentions` | bonus + note when description mentions H-1B/sponsorship |
| `min_score` | (informational) suggested `list` threshold |
| `db_path` | SQLite path (default `~/.jobsearch/jobs.db`) |
| `name`, `email`, `resume_path` | used in the exported application package |
| `weights` | override any scoring weight from `matcher.DEFAULT_WEIGHTS` |
| `adzuna` | `{app_id, app_key, country}` — or set `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` env vars |

## Tests

```bash
pip install -r requirements.txt
pytest -q
```

20 tests cover the matcher, the store (dedupe, lifecycle, filters), the source
adapters (HTTP stubbed), and the apply approval gate.

## Project layout

```
jobsearch/
  cli.py            argparse entry point (search/list/show/apply/status/stats)
  config.py         JSON config loading with QA/SDET-tuned defaults
  matcher.py        fit scoring: keywords, salary band, remote, sponsorship
  store.py          SQLite tracking + dedupe + status lifecycle
  apply.py          APPROVAL-GATED apply helper (dry-run / package export only)
  sources/
    base.py         Job dataclass + JobSource interface
    remotive.py     Remotive API (keyless)
    arbeitnow.py    Arbeitnow API (keyless)
    adzuna.py       Adzuna API (needs keys; degrades gracefully)
tests/              pytest suite (matcher, store, sources, apply)
config.example.json example config tuned for QA/SDET roles
.github/workflows/ci.yml   CI: install, pytest, CLI smoke test
```

## Adding a source

Subclass `jobsearch.sources.base.JobSource`, implement `fetch(query, limit)`
returning `list[Job]`, and register it in `jobsearch/sources/__init__.py`.
`available()` should return `(False, reason)` — never raise — when the source
can't run (e.g. missing credentials).
