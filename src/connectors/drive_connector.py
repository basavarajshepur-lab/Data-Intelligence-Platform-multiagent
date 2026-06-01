"""Google Drive connector — list and download CSV/JSON/SQL files."""

import io
import tempfile
from pathlib import Path

SUPPORTED_EXTENSIONS = {".csv", ".json", ".sql", ".ddl"}

_DRIVE_QUERY = (
    "trashed = false and ("
    "mimeType = 'text/csv' or "
    "name contains '.csv' or "
    "name contains '.json' or "
    "name contains '.sql' or "
    "name contains '.ddl'"
    ")"
)


def list_drive_files(max_results: int = 50) -> list[dict]:
    """Return CSV/JSON/SQL files from Google Drive, newest first."""
    from googleapiclient.discovery import build
    from .google_auth import get_credentials

    service = build("drive", "v3", credentials=get_credentials())

    result = (
        service.files()
        .list(
            q=_DRIVE_QUERY,
            pageSize=max_results,
            fields="files(id, name, mimeType, size, modifiedTime)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )

    files = []
    for f in result.get("files", []):
        # Filter by extension in case the MIME type is generic text/plain
        if any(f["name"].lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            files.append(
                {
                    "id": f["id"],
                    "name": f["name"],
                    "mime_type": f.get("mimeType", ""),
                    "size_bytes": int(f.get("size", 0)),
                    "modified": f.get("modifiedTime", ""),
                }
            )

    return files


def download_drive_file(file_id: str, filename: str) -> str:
    """Download a Drive file to a temp path. Returns the temp file path."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from .google_auth import get_credentials

    service = build("drive", "v3", credentials=get_credentials())

    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    suffix = Path(filename).suffix or ".csv"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(buf.getvalue())
    tmp.close()
    return tmp.name
