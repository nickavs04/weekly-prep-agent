from datetime import datetime, timedelta

import config
from google_auth import build_service


def _next_week_bounds() -> tuple[str, str]:
    """Return (monday_iso, saturday_iso) for the upcoming Mon-Fri work week."""
    today = datetime.now()
    # Days until next Monday (0=Mon … 6=Sun)
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # always jump to *next* Monday
    monday = (today + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    saturday = monday + timedelta(days=5)  # end of Friday
    return monday.isoformat() + "Z", saturday.isoformat() + "Z"


def get_client_meetings() -> list[dict]:
    """Fetch next week's calendar events that include at least one external attendee.

    Returns a list of dicts with keys:
        title, start, end, attendees (list of {email, name, external: bool})
    """
    service = build_service("calendar", "v3")
    time_min, time_max = _next_week_bounds()

    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
        maxResults=250,
    ).execute()

    meetings = []
    for event in events_result.get("items", []):
        attendees_raw = event.get("attendees", [])
        if not attendees_raw:
            continue

        attendees = []
        has_external = False
        for a in attendees_raw:
            email = a.get("email", "")
            external = not email.endswith(f"@{config.COMPANY_DOMAIN}")
            if external:
                has_external = True
            attendees.append({
                "email": email,
                "name": a.get("displayName", email),
                "external": external,
            })

        if not has_external:
            continue

        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))

        meetings.append({
            "title": event.get("summary", "(no title)"),
            "start": start,
            "end": end,
            "attendees": attendees,
        })

    return meetings
