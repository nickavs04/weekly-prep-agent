import json

import anthropic

import config

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
You are a meeting-prep assistant for a customer-facing team. Given structured \
data about a client account, produce a concise meeting preparation summary.

Format your output as plain text with the following sections (use Markdown-style \
headers). Omit a section entirely if there is no relevant data for it.

## Account Snapshot
Name, status, churn risk, segment.

## Products & ARR
Bulleted list of active products with ARR.

## Recent Email Activity
Key themes from recent email threads (2-3 sentences).

## Open Opportunities
Table or bullets: name, stage, amount, next step, close date.

## Upsell / Greenspace
Products they don't have, any recent upsell-click signals.

## Suggested Talking Points
3-5 actionable items to raise during the meeting.
"""


def generate_meeting_prep(
    meeting: dict,
    email_threads: list[dict],
    snowflake_data: dict,
) -> str:
    """Call Claude to produce a meeting prep summary for one client meeting."""

    user_content = json.dumps(
        {
            "meeting": {
                "title": meeting["title"],
                "start": meeting["start"],
                "attendees": meeting["attendees"],
            },
            "recent_emails": email_threads,
            "account_data": snowflake_data,
        },
        indent=2,
        default=str,
    )

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    return response.content[0].text
