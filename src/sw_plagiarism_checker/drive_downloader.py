"""
drive_downloader.py — Google Drive Integration
================================================
Downloads SolidWorks files (.sldprt, .sldasm) from a shared Google Drive
folder.  Supports OAuth2 authentication (first-run opens browser) and
caches credentials for subsequent runs.

Requirements
------------
pip install google-api-python-client google-auth-oauthlib
"""

import io
import os
import re
import sys
import json
import tempfile
from pathlib import Path

from .sldprt_parser import SUPPORTED_EXTENSIONS

# ---------------------------------------------------------------------------
# Lazy imports — these are optional dependencies
# ---------------------------------------------------------------------------

def _ensure_drive_deps():
    """Check that Google API libraries are installed."""
    try:
        from googleapiclient.discovery import build  # noqa: F401
        from google.auth.transport.requests import Request  # noqa: F401
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
    except ImportError:
        raise ImportError(
            "Google Drive support requires additional packages.\n"
            "Install them with:  pip install sw_plagiarism_checker[drive]\n"
            "  or:  pip install google-api-python-client google-auth-oauthlib"
        )


# ---------------------------------------------------------------------------
# URL / ID parsing
# ---------------------------------------------------------------------------

_FOLDER_URL_PATTERNS = [
    re.compile(r"drive\.google\.com/drive/(?:u/\d+/)?folders/([a-zA-Z0-9_-]+)"),
    re.compile(r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)"),
    re.compile(r"^([a-zA-Z0-9_-]{20,})$"),  # bare ID
]


def extract_folder_id(url_or_id: str) -> str:
    """Extract a Google Drive folder ID from a URL or bare ID string."""
    url_or_id = url_or_id.strip()
    for pattern in _FOLDER_URL_PATTERNS:
        m = pattern.search(url_or_id)
        if m:
            return m.group(1)
    raise ValueError(
        f"Could not extract a Google Drive folder ID from: {url_or_id}\n"
        "Expected a URL like: https://drive.google.com/drive/folders/<ID>"
    )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_DEFAULT_CREDS_FILE = "credentials.json"
_DEFAULT_TOKEN_FILE = "token.json"


def _get_credentials(credentials_path: str = None, token_path: str = None):
    """
    Obtain Google API credentials via OAuth2.
    On first run, opens a browser for consent.  Subsequent runs use cached token.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_path = credentials_path or _DEFAULT_CREDS_FILE
    token_path = token_path or _DEFAULT_TOKEN_FILE

    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Google API credentials file not found: {credentials_path}\n"
                    "Download it from https://console.cloud.google.com/apis/credentials\n"
                    "and place it in the current directory as 'credentials.json'."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_from_drive(
    folder_url_or_id: str,
    output_dir: str = None,
    credentials_path: str = None,
    token_path: str = None,
    progress_callback=None,
) -> list[str]:
    """
    Download all SolidWorks files from a Google Drive folder.

    Parameters
    ----------
    folder_url_or_id : str
        Google Drive folder URL or bare folder ID.
    output_dir : str, optional
        Directory to save downloaded files.  Defaults to a temp directory.
    credentials_path : str, optional
        Path to Google API credentials.json file.
    token_path : str, optional
        Path to cached OAuth2 token.
    progress_callback : callable, optional
        Called with (filename, current_index, total_count) for each file.

    Returns
    -------
    list[str]
        List of absolute paths to downloaded files.
    """
    _ensure_drive_deps()
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    folder_id = extract_folder_id(folder_url_or_id)
    creds = _get_credentials(credentials_path, token_path)
    service = build("drive", "v3", credentials=creds)

    # List files in folder
    sw_extensions = [ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS]
    query = (
        f"'{folder_id}' in parents and trashed = false"
    )

    all_files = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageSize=100,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        for f in resp.get("files", []):
            name = f.get("name", "")
            ext = os.path.splitext(name)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                all_files.append(f)

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    if not all_files:
        raise FileNotFoundError(
            f"No SolidWorks files found in Drive folder: {folder_id}\n"
            f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Create output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="sw_checker_")
    os.makedirs(output_dir, exist_ok=True)

    downloaded = []
    for idx, file_info in enumerate(all_files):
        file_id = file_info["id"]
        file_name = file_info["name"]

        if progress_callback:
            progress_callback(file_name, idx + 1, len(all_files))

        request = service.files().get_media(fileId=file_id)
        out_path = os.path.join(output_dir, file_name)

        with io.FileIO(out_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

        downloaded.append(os.path.abspath(out_path))

    return downloaded
