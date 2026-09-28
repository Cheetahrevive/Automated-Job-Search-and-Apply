"""Approval-gated apply flow.

HARD RULE: this module NEVER submits a job application over the network.
The only side effects it may ever produce are:

1. DRY-RUN (default): print a summary of what WOULD be prepared and show
   the job URL so the user can apply manually in their own browser.
2. PACKAGE EXPORT: after explicit, per-job, typed confirmation, write a
   prepared application package to disk (cover-note text + job details +
   resume path reference) for the user to attach themselves.

There is no HTTP POST, no form fill, no "submit" anywhere in this tool —
by design. If someone ever adds one, the name ``apply`` must stop
pretending it is approval-gated.
"""
from __future__ import annotations

import os
import sys
import webbrowser

from jobsearch.store import Store


def build_package_text(job: dict, config: dict) -> str:
    """Render the prepared application package (cover note + job reference)."""
    name = config.get("name") or "[Your Name]"
    email = config.get("email") or "[your email]"
    resume = config.get("resume_path") or "[path to your resume]"
    return f"""APPLICATION PACKAGE (prepared by jobsearch, NOT submitted)
=========================================================

Job      : {job['title']} @ {job['company']}
Source   : {job['source']} (id {job['id']})
Location : {job['location'] or 'n/a'}{' (remote)' if job['remote'] else ''}
Salary   : {job['salary_raw'] or 'not listed'}
Fit score: {job['fit_score']}
Apply at : {job['url']}

--- Cover note draft (edit before use) -------------------
Dear Hiring Manager at {job['company']},

I am applying for the {job['title']} role. As a QA automation engineer
with deep experience in Selenium, Playwright, API testing and CI/CD,
I believe I am a strong fit. Details are in my attached resume.

Name  : {name}
Email : {email}
Resume: {resume}

--- End of draft -----------------------------------------

This package was generated locally. Nothing was sent anywhere.
Apply manually at the URL above.
"""


def dry_run_summary(job: dict, config: dict, open_browser: bool = False) -> None:
    print("=== APPLY (dry-run — nothing will be submitted) ===")
    print(f"Job      : {job['title']} @ {job['company']}")
    print(f"Fit score: {job['fit_score']} | status: {job['status']}")
    print(f"Apply URL: {job['url'] or '(no URL available)'}")
    print()
    print("What WOULD happen with --confirm:")
    print("  1. Write a prepared application package (cover-note text +")
    print("     job details + resume reference) to a local file.")
    print("  2. Mark the job as 'applied' in the local SQLite store.")
    print()
    print("What will NEVER happen: automatic submission. This tool cannot")
    print("submit applications; you apply manually in your own browser.")
    if open_browser and job["url"]:
        print("Opening the job URL in your browser for manual application...")
        webbrowser.open(job["url"])


def export_package(job: dict, config: dict, out_dir: str,
                   store: Store, confirm_token: str) -> str:
    """Write the application package to disk. Requires the caller to have
    collected explicit typed confirmation already."""
    os.makedirs(out_dir, exist_ok=True)
    safe_company = "".join(c if c.isalnum() else "_" for c in job["company"])[:40]
    filename = f"apply_{job['id']}_{safe_company}.txt"
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_package_text(job, config))
    store.set_status(job["id"], "applied")
    return path


def ask_confirmation(job_id: int, non_interactive_token: str | None) -> bool:
    """Explicit, per-job, typed confirmation.

    Interactive: the user must type the numeric job id shown on screen.
    Non-interactive: --confirm <job-id> with the same id.
    Anything else => no confirmation.
    """
    if non_interactive_token is not None:
        return non_interactive_token.strip() == str(job_id)
    try:
        answer = input(
            f"To export the application package for job {job_id}, type the job id "
            f"({job_id}) and press Enter (anything else cancels): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return False
    return answer == str(job_id)


def cmd_apply(job: dict, config: dict, store: Store,
              confirm: str | None, out_dir: str) -> int:
    if confirm is None:
        dry_run_summary(job, config)
        return 0
    if not ask_confirmation(job["id"], confirm):
        print("Confirmation did not match — no package exported, nothing changed.")
        return 2
    path = export_package(job, config, out_dir, store, confirm)
    print(f"Application package written to: {path}")
    print(f"Job {job['id']} marked as 'applied' in the local store.")
    print("Nothing was submitted. Apply manually at:", job["url"] or "(no URL)")
    return 0
