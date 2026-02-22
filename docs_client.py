from datetime import datetime, timedelta

import config
from google_auth import build_service


def _next_monday_label() -> str:
    """Return a human-readable label like 'Week of Feb 23, 2026'."""
    today = datetime.now()
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    monday = today + timedelta(days=days_ahead)
    return monday.strftime("Week of %b %-d, %Y")


def append_to_doc(sections: list[dict]) -> None:
    """Append meeting-prep sections to the running Google Doc.

    Each item in *sections* should have keys: title (meeting title) and body
    (the Claude-generated summary text).
    """
    service = build_service("docs", "v1")

    # Build the list of insertText requests (inserted at the end of the doc).
    # Google Docs insertText index 1 = start of document, but we want the end,
    # so we first fetch the doc to get the endIndex.
    doc = service.documents().get(documentId=config.GOOGLE_DOC_ID).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1  # before trailing newline

    week_label = _next_monday_label()

    # We build text blocks and batch-insert them.  All inserts are at *end_index*
    # and we track the running offset.
    requests: list[dict] = []
    offset = end_index

    def _insert(text: str, bold: bool = False, font_size: int | None = None, heading: str | None = None):
        nonlocal offset
        requests.append({
            "insertText": {
                "location": {"index": offset},
                "text": text,
            }
        })
        start = offset
        end = offset + len(text)

        if bold or font_size:
            style: dict = {}
            fields = []
            if bold:
                style["bold"] = True
                fields.append("bold")
            if font_size:
                style["fontSize"] = {"magnitude": font_size, "unit": "PT"}
                fields.append("fontSize")
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "textStyle": style,
                    "fields": ",".join(fields),
                }
            })

        if heading:
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": heading},
                    "fields": "namedStyleType",
                }
            })

        offset = end

    # --- Week header ---
    _insert(f"\n{'=' * 60}\n")
    _insert(f"{week_label}\n", heading="HEADING_1")

    for section in sections:
        _insert(f"\n--- {section['title']} ---\n", bold=True, font_size=12)
        _insert(section["body"] + "\n")

    # Execute batch update
    service.documents().batchUpdate(
        documentId=config.GOOGLE_DOC_ID,
        body={"requests": requests},
    ).execute()
