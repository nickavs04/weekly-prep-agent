import json

import anthropic

import config

client = anthropic.AnthropicBedrock(aws_region=config.AWS_REGION)

SYSTEM_PROMPT = """\
You are a meeting-prep assistant for a customer-facing team. Given structured \
data about a client account, produce a concise meeting preparation summary.

Format your output as plain text with EXACTLY the following sections and field \
labels (use Markdown-style headers). Follow the formatting rules precisely.

## Account Snapshot
Name: <account name from account_data, or the company name from the meeting title>
Carta Account Link (IS): <if account_id is available, output the link \
https://app.carta.com/account/<account_id> — otherwise output "N/A">
Client Health Score (Green, Yellow, or Red): <map the CHURN_SCORE from \
account_data: low churn risk = Green, moderate = Yellow, high = Red. \
If no score is available, write "Unknown">
Invited Guests: <list external attendees from the meeting, with name and role \
if available, separated by semicolons>
Purchased Features - IS: <semicolon-separated list of active subscription \
PRODUCT_NAMEs from account_data. If none, write "None on file">

If no CRM account data was found (account_id is null), add a note after the \
fields:

Note: No CRM account data was found for <company name>. This may be a prospect \
or an account not yet fully onboarded in the system. Recommend confirming \
account status before the meeting.

## Recent Email Activity
Write a short paragraph (2-4 sentences) summarising the key themes from the \
recent email threads. Mention specific people, dates, and topics discussed. \
Call out any actionable signals (pricing questions, support issues, renewal \
conversations, escalations). If there are no email threads, write \
"No recent email activity found."

## Suggested Talking Points
Provide 3-5 numbered talking points. Each should have a **bold title** followed \
by a colon and a 1-2 sentence explanation that is specific to this account and \
meeting context. Focus on actionable items the attendee should raise or prepare \
for during the meeting.
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
        model="us.anthropic.claude-opus-4-6-v1",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    return response.content[0].text
