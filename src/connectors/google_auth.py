"""Shared Google OAuth2 authentication for Gmail and Drive.

First-time setup:
1. Create a project at console.cloud.google.com
2. Enable Gmail API and Google Drive API
3. Create OAuth 2.0 credentials (type: Desktop App)
4. Download credentials.json and place it in the project root
5. In the app, click "Connect Google Account" and complete the browser flow
"""

import threading
from pathlib import Path
from typing import Optional

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_CREDS_FILE = Path("credentials.json")
_TOKEN_FILE = Path("google_token.json")


def credentials_file_exists() -> bool:
    return _CREDS_FILE.exists()


def is_authenticated() -> bool:
    if not _TOKEN_FILE.exists():
        return False
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)
        return creds.valid or bool(creds.refresh_token)
    except Exception:
        return False


def get_credentials():
    """Return valid credentials, refreshing the access token if expired."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not _TOKEN_FILE.exists():
        raise RuntimeError("Not authenticated. Complete the Google authorization flow first.")

    creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _TOKEN_FILE.write_text(creds.to_json())

    return creds


def _run_oauth_flow(status: dict, port: int = 8502) -> None:
    """Background thread: open browser OAuth flow and save the token file."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(str(_CREDS_FILE), SCOPES)
        creds = flow.run_local_server(port=port, open_browser=True)
        _TOKEN_FILE.write_text(creds.to_json())
        status["done"] = True
        status["error"] = None
    except Exception as exc:
        status["done"] = True
        status["error"] = str(exc)


def start_auth_thread(port: int = 8502) -> dict:
    """Kick off the OAuth flow in a daemon thread. Poll returned dict for completion."""
    status: dict = {"done": False, "error": None}
    threading.Thread(target=_run_oauth_flow, args=(status, port), daemon=True).start()
    return status


def revoke() -> None:
    """Remove the stored token (disconnect)."""
    if _TOKEN_FILE.exists():
        _TOKEN_FILE.unlink()
