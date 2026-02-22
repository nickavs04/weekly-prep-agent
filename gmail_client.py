import base64
from datetime import datetime, timedelta

from google_auth import build_service


def get_recent_threads(email: str, days: int = 14, max_threads: int = 10) -> list[dict]:
    """Search Gmail for recent threads involving *email* within the last *days* days.

    Returns a list of dicts with keys: subject, snippet, date.
    """
    service = build_service("gmail", "v1")

    after_date = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
    query = f"from:{email} OR to:{email} after:{after_date}"

    results = service.users().threads().list(
        userId="me",
        q=query,
        maxResults=max_threads,
    ).execute()

    threads = []
    for t in results.get("threads", []):
        thread = service.users().threads().get(
            userId="me",
            id=t["id"],
            format="metadata",
            metadataHeaders=["Subject", "Date"],
        ).execute()

        messages = thread.get("messages", [])
        if not messages:
            continue

        # Pull headers from the first message in the thread
        headers = {h["name"]: h["value"] for h in messages[0].get("payload", {}).get("headers", [])}

        threads.append({
            "subject": headers.get("Subject", "(no subject)"),
            "snippet": messages[0].get("snippet", ""),
            "date": headers.get("Date", ""),
        })

    return threads
