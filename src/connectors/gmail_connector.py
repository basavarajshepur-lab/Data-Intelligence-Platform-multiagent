"""Gmail connector — list emails with CSV/JSON/SQL attachments and download them."""

import base64
import os
import tempfile
from pathlib import Path

SUPPORTED_EXTENSIONS = {".csv", ".json", ".sql", ".ddl"}


def list_emails_with_attachments(max_results: int = 30) -> list[dict]:
    """Return recent emails that have CSV/JSON/SQL file attachments."""
    from googleapiclient.discovery import build
    from .google_auth import get_credentials

    service = build("gmail", "v1", credentials=get_credentials())

    query = "has:attachment (filename:*.csv OR filename:*.json OR filename:*.sql OR filename:*.ddl)"
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    raw_msgs = result.get("messages", [])

    emails = []
    for raw in raw_msgs:
        detail = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=raw["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
            .execute()
        )
        headers = {
            h["name"]: h["value"]
            for h in detail.get("payload", {}).get("headers", [])
        }

        attachments = []
        for part in detail.get("payload", {}).get("parts", []):
            fname = part.get("filename", "")
            if fname and Path(fname).suffix.lower() in SUPPORTED_EXTENSIONS:
                attachments.append(
                    {
                        "filename": fname,
                        "attachment_id": part.get("body", {}).get("attachmentId"),
                        "size_bytes": part.get("body", {}).get("size", 0),
                    }
                )

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
