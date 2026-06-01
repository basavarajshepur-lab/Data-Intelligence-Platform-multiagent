"""Gmail connector — list emails with CSV/JSON/SQL attachments and download them."""

import base64
import tempfile
from pathlib import Path

SUPPORTED_EXTENSIONS = {".csv", ".json", ".sql", ".ddl"}


def _collect_attachments(parts: list, result: list) -> None:
    """Recursively walk a message part tree to collect attachment metadata."""
    for part in parts:
        fname = part.get("filename", "")
        body = part.get("body", {})
        # A real attachment has a filename and an attachmentId
        if fname and Path(fname).suffix.lower() in SUPPORTED_EXTENSIONS and body.get("attachmentId"):
            result.append(
                {
                    "filename": fname,
                    "attachment_id": body["attachmentId"],
                    "size_bytes": body.get("size", 0),
                }
            )
        # Recurse into nested multipart containers
        sub_parts = part.get("parts", [])
        if sub_parts:
            _collect_attachments(sub_parts, result)


def list_emails_with_attachments(max_results: int = 30) -> list[dict]:
    """Return recent emails that have CSV/JSON/SQL file attachments."""
    from googleapiclient.discovery import build
    from .google_auth import get_credentials

    service = build("gmail", "v1", credentials=get_credentials())

    # Gmail search: filename: operator matches substrings — ".csv" matches any *.csv attachment
    query = "has:attachment (filename:.csv OR filename:.json OR filename:.sql OR filename:.ddl)"
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    raw_msgs = result.get("messages", [])

    emails = []
    for raw in raw_msgs:
        # format="full" is required to get the parts tree with attachmentId values
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=raw["id"], format="full")
            .execute()
        )
        payload = detail.get("payload", {})
        headers = {
            h["name"]: h["value"] for h in payload.get("headers", [])
        }

        attachments: list[dict] = []
        _collect_attachments(payload.get("parts", []), attachments)

        if attachments:
            emails.append(
                {
                    "message_id": raw["id"],
                    "subject": headers.get("Subject", "(no subject)"),
                    "sender": headers.get("From", "Unknown"),
                    "date": headers.get("Date", ""),
                    "attachments": attachments,
                }
            )

    return emails


def download_attachment(message_id: str, attachment_id: str, filename: str) -> str:
    """Download a Gmail attachment to a temp file. Returns the temp file path."""
    from googleapiclient.discovery import build
    from .google_auth import get_credentials

    service = build("gmail", "v1", credentials=get_credentials())

    raw = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    data = base64.urlsafe_b64decode(raw["data"])

    suffix = Path(filename).suffix or ".csv"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name
