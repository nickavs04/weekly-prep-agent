#!/usr/bin/env python3
"""Weekly Client Meeting Prep Agent — orchestrator.

Run:
    python main.py            # full run: fetch data, summarise, write to Google Doc
    python main.py --dry-run  # print summaries to stdout without writing to the Doc
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import config  # noqa: F401 — forces early .env load & validation
from calendar_client import get_client_meetings
from gmail_client import get_recent_threads
from snowflake_client import get_all_account_data
from summarizer import generate_meeting_prep
from docs_client import append_to_doc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _external_domains(meeting: dict) -> set[str]:
    """Extract unique external email domains from a meeting's attendees."""
    domains: set[str] = set()
    for a in meeting["attendees"]:
        if a["external"]:
            domain = a["email"].split("@")[-1].lower()
            domains.add(domain)
    return domains


def _external_emails(meeting: dict) -> list[str]:
    return [a["email"] for a in meeting["attendees"] if a["external"]]


def _fetch_data_for_meeting(meeting: dict) -> dict:
    """Fetch Gmail threads and Snowflake data for a single meeting (runs in a thread)."""
    domains = _external_domains(meeting)
    external_emails = _external_emails(meeting)

    # Gmail: search for each external attendee
    all_threads: list[dict] = []
    for email in external_emails:
        all_threads.extend(get_recent_threads(email))

    # Snowflake: query for the first domain that resolves to an account
    snowflake_data: dict = {
        "account_id": None,
        "overview": None,
        "subscriptions": [],
        "opportunities": [],
        "upsell_signals": [],
        "greenspace": [],
        "product_usage": [],
    }
    for domain in domains:
        data = get_all_account_data(domain)
        if data["account_id"]:
            snowflake_data = data
            break

    return {
        "meeting": meeting,
        "email_threads": all_threads,
        "snowflake_data": snowflake_data,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly Client Meeting Prep Agent")
    parser.add_argument("--dry-run", action="store_true", help="Print summaries without writing to Google Doc")
    args = parser.parse_args()

    # 1. Calendar — upcoming client meetings
    print("Fetching upcoming client meetings …")
    meetings = get_client_meetings()
    if not meetings:
        print("No client meetings found for next week.")
        return
    print(f"  Found {len(meetings)} meeting(s) with external attendees.\n")

    # 2. Gather Gmail + Snowflake data in parallel
    print("Gathering email threads and Snowflake data …")
    gathered: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_data_for_meeting, m): m for m in meetings}
        for future in as_completed(futures):
            gathered.append(future.result())
    print(f"  Data gathered for {len(gathered)} meeting(s).\n")

    # 3. Generate Claude summaries
    print("Generating meeting prep summaries with Claude …")
    sections: list[dict] = []
    for item in gathered:
        summary = generate_meeting_prep(
            meeting=item["meeting"],
            email_threads=item["email_threads"],
            snowflake_data=item["snowflake_data"],
        )
        sections.append({
            "title": item["meeting"]["title"],
            "body": summary,
        })
        print(f"  ✓ {item['meeting']['title']}")

    # 4. Output
    if args.dry_run:
        print("\n--- DRY RUN (not writing to Google Doc) ---\n")
        for s in sections:
            print(f"=== {s['title']} ===")
            print(s["body"])
            print()
    else:
        print("\nAppending to Google Doc …")
        append_to_doc(sections)
        print("Done. Check your Google Doc for the updated prep notes.")


if __name__ == "__main__":
    main()
