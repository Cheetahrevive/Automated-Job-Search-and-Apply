"""Config loading: JSON file + CLI overrides."""
from __future__ import annotations

import json
import os

DEFAULTS: dict = {
    "query": "QA automation engineer",
    "sources": ["remotive", "arbeitnow"],
    "limit_per_source": 50,
    "include_keywords": [
        "qa", "quality assurance", "sdet", "test automation",
        "playwright", "selenium", "api testing", "python",
    ],
    "exclude_keywords": [
        "senior director", "vp ", "principal architect", "manual only",
    ],
    "salary_min": 100000,
    "salary_max": None,
    "remote_only": False,
    "prefer_sponsorship_mentions": True,
    "min_score": 50,
    "db_path": "~/.jobsearch/jobs.db",
    "resume_path": "",
    "name": "",
    "email": "",
    "weights": {},
}


def load_config(path: str | None) -> dict:
    config = dict(DEFAULTS)
    if path:
        expanded = os.path.expanduser(path)
        with open(expanded, encoding="utf-8") as fh:
            user = json.load(fh)
        if not isinstance(user, dict):
            raise ValueError(f"config {path} must be a JSON object")
        config.update(user)
    config["db_path"] = os.path.expanduser(config["db_path"])
    return config
