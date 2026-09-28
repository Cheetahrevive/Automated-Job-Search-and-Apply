"""CLI entry point: python -m jobsearch.cli <command> [options]

Commands:
  search   fetch from sources, score, store
  list     show stored matches (filterable by min score / status)
  show     full details of one job
  apply    approval-gated apply helper (dry-run by default)
  stats    pipeline summary
"""
from __future__ import annotations

import argparse
import sys

from jobsearch import apply as apply_mod
from jobsearch.config import load_config
from jobsearch.matcher import score_job
from jobsearch.sources import SOURCES
from jobsearch.sources.adzuna import AdzunaSource
from jobsearch.store import Store


def _configure_adzuna(config: dict) -> None:
    adz = config.get("adzuna", {})
    SOURCES["adzuna"] = AdzunaSource(
        app_id=adz.get("app_id"),
        app_key=adz.get("app_key"),
        country=adz.get("country", "us"),
    )


def cmd_search(args, config: dict) -> int:
    _configure_adzuna(config)
    store = Store(config["db_path"])
    query = args.query or config["query"]
    sources = args.sources or config["sources"]
    limit = args.limit or config["limit_per_source"]

    total_new = total_updated = 0
    notes_for: dict = {}
    jobs = []
    for name in sources:
        src = SOURCES.get(name)
        if src is None:
            print(f"! unknown source '{name}' — skipped", file=sys.stderr)
            continue
        ok, reason = src.available()
        if not ok:
            print(f"! source '{name}' unavailable: {reason}", file=sys.stderr)
            continue
        try:
            fetched = src.fetch(query, limit)
        except Exception as exc:  # network/API hiccup: skip, don't die
            print(f"! source '{name}' failed: {exc}", file=sys.stderr)
            continue
        print(f"* {name}: fetched {len(fetched)}")
        for job in fetched:
            score, matched, notes = score_job(job, config)
            job.fit_score = score
            notes_for[(job.source, job.external_id)] = "; ".join(matched + notes)
            jobs.append(job)

    inserted, updated = store.upsert_jobs(jobs, notes_for)
    print(f"stored: {inserted} new, {updated} updated (db: {config['db_path']})")
    store.close()
    return 0


def cmd_list(args, config: dict) -> int:
    store = Store(config["db_path"])
    rows = store.list(min_score=args.min_score, status=args.status, limit=args.limit)
    if not rows:
        print("No jobs match. Run `search` first.")
    for r in rows:
        remote = " [remote]" if r["remote"] else ""
        print(
            f"#{r['id']:>4}  {r['fit_score']:>5.1f}  [{r['status']:<8}] "
            f"{r['title'][:55]:<55} @ {r['company'][:30]}{remote}"
        )
    store.close()
    return 0


def cmd_show(args, config: dict) -> int:
    store = Store(config["db_path"])
    job = store.get(args.job_id)
    if not job:
        print(f"No job with id {args.job_id}.", file=sys.stderr)
        return 1
    print(f"#{job['id']}  {job['title']} @ {job['company']}")
    print(f"Source   : {job['source']} / {job['external_id']}")
    print(f"Location : {job['location'] or 'n/a'}{' (remote)' if job['remote'] else ''}")
    print(f"Salary   : {job['salary_raw'] or 'not listed'}")
    print(f"Posted   : {job['posted_at'] or 'n/a'}")
    print(f"Score    : {job['fit_score']}  Status: {job['status']}")
    print(f"URL      : {job['url']}")
    print(f"Tags     : {job['tags']}")
    print(f"Notes    : {job['notes']}")
    desc = (job["description"] or "")[:1500]
    print(f"\n--- description (truncated) ---\n{desc}")
    store.close()
    return 0


def cmd_apply(args, config: dict) -> int:
    store = Store(config["db_path"])
    job = store.get(args.job_id)
    if not job:
        print(f"No job with id {args.job_id}.", file=sys.stderr)
        return 1
    rc = apply_mod.cmd_apply(job, config, store, args.confirm, args.out_dir)
    store.close()
    return rc


def cmd_status(args, config: dict) -> int:
    store = Store(config["db_path"])
    try:
        ok = store.set_status(args.job_id, args.new_status)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not ok:
        print(f"No job with id {args.job_id}.", file=sys.stderr)
        return 1
    print(f"Job {args.job_id} -> {args.new_status}")
    store.close()
    return 0


def cmd_stats(args, config: dict) -> int:
    store = Store(config["db_path"])
    s = store.stats()
    print(f"Total jobs stored : {s['total']}")
    print("By status:")
    for status, n in sorted(s["by_status"].items()):
        print(f"  {status:<10} {n}")
    print("By source:")
    for source, n in sorted(s["by_source"].items()):
        print(f"  {source:<10} {n}")
    print(f"Avg fit score (new): {s['avg_score_new']}")
    store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jobsearch",
        description="Approval-gated job-search automation. Never auto-submits applications.",
    )
    p.add_argument("--config", "-c", default=None, help="path to JSON config file")
    p.add_argument("--db", default=None, help="override SQLite db path")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="fetch from sources, score, store")
    s.add_argument("--query", "-q", default=None)
    s.add_argument("--sources", nargs="+", default=None,
                   choices=list(SOURCES), help="which sources to use")
    s.add_argument("--limit", type=int, default=None, help="jobs per source")

    l = sub.add_parser("list", help="show stored matches")
    l.add_argument("--min-score", type=float, default=0)
    l.add_argument("--status", default=None,
                   choices=["new", "reviewed", "saved", "skipped", "applied"])
    l.add_argument("--limit", type=int, default=50)

    sh = sub.add_parser("show", help="full details of one job")
    sh.add_argument("job_id", type=int)

    a = sub.add_parser(
        "apply",
        help="approval-gated apply helper (dry-run unless --confirm <job-id>)",
    )
    a.add_argument("job_id", type=int)
    a.add_argument(
        "--confirm", default=None, metavar="JOB_ID",
        help="type the job id to confirm package export (approval gate)",
    )
    a.add_argument("--out-dir", default="./applications",
                   help="where to write the application package")

    st = sub.add_parser("status", help="set a job's status (reviewed/saved/skipped/applied)")
    st.add_argument("job_id", type=int)
    st.add_argument("new_status", choices=["new", "reviewed", "saved", "skipped", "applied"])

    sub.add_parser("stats", help="pipeline summary")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.db:
        config["db_path"] = args.db
    handler = {
        "search": cmd_search,
        "list": cmd_list,
        "show": cmd_show,
        "apply": cmd_apply,
        "status": cmd_status,
        "stats": cmd_stats,
    }[args.command]
    return handler(args, config)


if __name__ == "__main__":
    sys.exit(main())
