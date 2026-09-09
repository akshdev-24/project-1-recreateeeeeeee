"""
YouTube uploader for the Shayari Shorts automation project.

Features:
- Google OAuth using client_secrets.json / credentials.json
- Reuses saved refresh-token credentials
- Uploads videos through YouTube Data API v3
- Privacy is ALWAYS hard-coded to UNLISTED
- Robust YouTube tag sanitization
- Prevents invalid/duplicate/oversized tags
- Compatible with main.py:
      upload_short_to_youtube(
          video_path,
          title,
          description,
          tags=tags
      )
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"

OUTPUT_DIR = BASE_DIR / "output"


# ============================================================
# YOUTUBE CONFIGURATION
# ============================================================

YOUTUBE_UPLOAD_SCOPE = [
    "https://www.googleapis.com/auth/youtube.upload"
]

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# IMPORTANT:
# Uploads are NEVER public.
PRIVACY_STATUS = "unlisted"

DEFAULT_CATEGORY_ID = "22"

# YouTube's tag metadata has a combined character limit.
# We intentionally stay below the maximum for safety.
MAX_TOTAL_TAG_CHARS = 450

# Individual tags are also kept short.
MAX_SINGLE_TAG_CHARS = 100

# Maximum number of tags we will send.
MAX_TAG_COUNT = 50


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)

if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


# ============================================================
# FILE VALIDATION
# ============================================================

def validate_files() -> None:
    """
    Validate OAuth files and project paths before upload.
    """

    print()
    print("=" * 70)
    print("🔐 CHECKING YOUTUBE OAUTH FILES")
    print("=" * 70)

    if not CLIENT_SECRETS_FILE.exists():
        raise FileNotFoundError(
            "\n"
            "client_secrets.json not found.\n\n"
            f"Expected location:\n"
            f"{CLIENT_SECRETS_FILE}\n\n"
            "Create/download your OAuth client JSON from Google Cloud Console."
        )

    if not CLIENT_SECRETS_FILE.is_file():
        raise FileNotFoundError(
            f"client_secrets.json exists but is not a file:\n"
            f"{CLIENT_SECRETS_FILE}"
        )

    print("✅ client_secrets.json found")

    if CREDENTIALS_FILE.exists():
        if not CREDENTIALS_FILE.is_file():
            raise FileNotFoundError(
                f"credentials.json exists but is not a file:\n"
                f"{CREDENTIALS_FILE}"
            )

        print("✅ credentials.json found")
    else:
        print(
            "⚠️ credentials.json not found. "
            "OAuth authorization will be required."
        )


# ============================================================
# OAUTH
# ============================================================

def get_credentials() -> Credentials:
    """
    Load existing YouTube OAuth credentials.

    If credentials are expired and contain a refresh token,
    refresh them automatically.

    If no valid credentials exist, launch OAuth authorization.
    """

    credentials: Credentials | None = None

    # --------------------------------------------------------
    # Load saved credentials
    # --------------------------------------------------------

    if CREDENTIALS_FILE.exists():
        try:
            print("🔑 Loading saved YouTube credentials...")

            credentials = Credentials.from_authorized_user_file(
                str(CREDENTIALS_FILE),
                YOUTUBE_UPLOAD_SCOPE,
            )

        except Exception as exc:
            logger.warning(
                "Could not load credentials.json: %s",
                exc,
            )
            credentials = None

    # --------------------------------------------------------
    # Existing valid credentials
    # --------------------------------------------------------

    if credentials and credentials.valid:
        print("✅ YouTube credentials are valid.")
        return credentials

    # --------------------------------------------------------
    # Refresh expired credentials
    # --------------------------------------------------------

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            print("🔄 Refreshing YouTube OAuth credentials...")

            credentials.refresh(Request())

            CREDENTIALS_FILE.write_text(
                credentials.to_json(),
                encoding="utf-8",
            )

            print("✅ YouTube credentials refreshed.")

            return credentials

        except Exception as exc:
            logger.warning(
                "Credential refresh failed: %s",
                exc,
            )

            credentials = None

    # --------------------------------------------------------
    # New OAuth authorization
    # --------------------------------------------------------

    print()
    print("🌐 Starting YouTube OAuth authorization...")
    print(
        "If this is the first authorization, "
        "a browser window may open."
    )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        YOUTUBE_UPLOAD_SCOPE,
    )

    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    CREDENTIALS_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    print("✅ YouTube OAuth credentials saved.")

    return credentials


# ============================================================
# AUTHENTICATED YOUTUBE CLIENT
# ============================================================

def get_authenticated_service():
    """
    Initialize authenticated YouTube API client.
    """

    validate_files()

    credentials = get_credentials()

    youtube = build(
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        credentials=credentials,
        cache_discovery=False,
    )

    print("✅ YouTube API client initialized.")

    return youtube


# ============================================================
# TAG NORMALIZATION
# ============================================================

def _flatten_tags(tags) -> list[str]:
    """
    Convert any supported tag input into a flat list.

    Supported:
    - list
    - tuple
    - set
    - string
    - comma-separated string
    - newline-separated string
    """

    if tags is None:
        return []

    if isinstance(tags, str):
        raw_items = re.split(r"[,;\n\r]+", tags)

    elif isinstance(tags, Iterable):
        raw_items = []

        for item in tags:
            if item is None:
                continue

            if isinstance(item, str):
                # A list item may itself contain commas/newlines.
                raw_items.extend(
                    re.split(r"[,;\n\r]+", item)
                )
            else:
                raw_items.append(str(item))

    else:
        raw_items = [str(tags)]

    return raw_items


def _clean_single_tag(tag: str) -> str:
    """
    Clean one YouTube tag.
    """

    tag = str(tag)

    # Remove leading/trailing whitespace.
    tag = tag.strip()

    # Remove surrounding quotation marks.
    tag = tag.strip("\"'")

    # Remove hashtag symbols.
    #
    # This is important because hashtags belong in the title/
    # description, while YouTube API tags should be plain keywords.
    tag = tag.replace("#", "")

    # Collapse repeated whitespace.
    tag = re.sub(r"\s+", " ", tag)

    # YouTube tag should not contain line breaks.
    tag = tag.replace("\n", " ")
    tag = tag.replace("\r", " ")

    # Strip again after replacements.
    tag = tag.strip()

    # Individual safety limit.
    if len(tag) > MAX_SINGLE_TAG_CHARS:
        tag = tag[:MAX_SINGLE_TAG_CHARS].rstrip()

    return tag


def sanitize_youtube_tags(tags) -> list[str]:
    """
    Convert arbitrary tag input into safe YouTube API tags.

    Safety rules:
    - Removes # symbols
    - Removes empty tags
    - Removes duplicates
    - Removes line breaks
    - Splits comma/newline-separated input
    - Limits individual tags
    - Limits total tag characters
    - Limits total tag count
    """

    raw_tags = _flatten_tags(tags)

    cleaned: list[str] = []
    seen: set[str] = set()

    total_chars = 0

    for raw_tag in raw_tags:

        tag = _clean_single_tag(raw_tag)

        if not tag:
            continue

        # Case-insensitive duplicate protection.
        duplicate_key = tag.casefold()

        if duplicate_key in seen:
            continue

        # YouTube tag limit.
        if len(cleaned) >= MAX_TAG_COUNT:
            break

        # Account for separators between tags.
        separator_cost = 1 if cleaned else 0

        if total_chars + separator_cost + len(tag) > MAX_TOTAL_TAG_CHARS:
            break

        cleaned.append(tag)
        seen.add(duplicate_key)

        total_chars += separator_cost + len(tag)

    return cleaned


# ============================================================
# TAG VALIDATION
# ============================================================

def validate_youtube_tags(tags: list[str]) -> None:
    """
    Final validation before sending metadata to YouTube.
    """

    if not isinstance(tags, list):
        raise TypeError("YouTube tags must be a list.")

    if len(tags) > MAX_TAG_COUNT:
        raise ValueError(
            f"Too many YouTube tags: {len(tags)} "
            f"(maximum allowed by uploader: {MAX_TAG_COUNT})"
        )

    total_length = 0

    for index, tag in enumerate(tags):

        if not isinstance(tag, str):
            raise TypeError(
                f"YouTube tag #{index + 1} is not a string."
            )

        if not tag.strip():
            raise ValueError(
                f"YouTube tag #{index + 1} is empty."
            )

        if "#" in tag:
            raise ValueError(
                f"YouTube tag #{index + 1} still contains '#': {tag!r}"
            )

        if "\n" in tag or "\r" in tag:
            raise ValueError(
                f"YouTube tag #{index + 1} contains a line break."
            )

        if len(tag) > MAX_SINGLE_TAG_CHARS:
            raise ValueError(
                f"YouTube tag #{index + 1} is too long."
            )

        if index > 0:
            total_length += 1

        total_length += len(tag)

    if total_length > MAX_TOTAL_TAG_CHARS:
        raise ValueError(
            "YouTube tags exceed the safe combined character limit: "
            f"{total_length} > {MAX_TOTAL_TAG_CHARS}"
        )


# ============================================================
# DESCRIPTION CLEANUP
# ============================================================

def sanitize_description(description) -> str:
    """
    Keep description safe and predictable.

    The description is NOT generated here.
    It comes from the user's local assets/metadata.
    """

    if description is None:
        return ""

    description = str(description)

    # Remove null bytes.
    description = description.replace("\x00", "")

    # Normalize Windows line endings.
    description = description.replace("\r\n", "\n")
    description = description.replace("\r", "\n")

    return description.strip()


# ============================================================
# TITLE CLEANUP
# ============================================================

def sanitize_title(title) -> str:
    """
    Clean title without generating or rewriting its SEO content.
    """

    if title is None:
        title = ""

    title = str(title)

    title = title.replace("\x00", "")

    title = title.replace("\r\n", " ")
    title = title.replace("\r", " ")
    title = title.replace("\n", " ")

    title = re.sub(r"\s+", " ", title).strip()

    if not title:
        raise ValueError("YouTube video title cannot be empty.")

    # YouTube title maximum is 100 characters.
    if len(title) > 100:
        title = title[:100].rstrip()

    return title


# ============================================================
# CATEGORY
# ============================================================

def get_category_id() -> str:
    """
    Get YouTube category ID.

    Defaults to 22 (People & Blogs).
    """

    category = os.getenv(
        "YOUTUBE_CATEGORY_ID",
        DEFAULT_CATEGORY_ID,
    ).strip()

    if not category:
        category = DEFAULT_CATEGORY_ID

    return category


# ============================================================
# UPLOAD VIDEO
# ============================================================

def upload_video(
    youtube,
    video_path: str | Path,
    title: str,
    description: str,
    tags=None,
    category_id: str | None = None,
):
    """
    Upload a video to YouTube.

    IMPORTANT:
    Privacy is always UNLISTED.
    """

    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(
            f"Video file not found:\n{video_path}"
        )

    if not video_path.is_file():
        raise FileNotFoundError(
            f"Video path is not a file:\n{video_path}"
        )

    if video_path.stat().st_size <= 0:
        raise ValueError(
            f"Video file is empty:\n{video_path}"
        )

    # --------------------------------------------------------
    # Sanitize metadata
    # --------------------------------------------------------

    title = sanitize_title(title)
    description = sanitize_description(description)

    safe_tags = sanitize_youtube_tags(tags)

    validate_youtube_tags(safe_tags)

    if category_id is None:
        category_id = get_category_id()

    category_id = str(category_id).strip() or DEFAULT_CATEGORY_ID

    # --------------------------------------------------------
    # Upload metadata
    # --------------------------------------------------------

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": safe_tags,
            "categoryId": category_id,
        },

        # HARD-CODED SAFETY:
        # NEVER change this to public.
        "status": {
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }

    print()
    print("=" * 70)
    print("📤 YOUTUBE UPLOAD")
    print("=" * 70)

    print(f"File: {video_path}")
    print(f"Title: {title}")
    print(f"Tags: {len(safe_tags)}")
    print(
        "Tag characters:",
        sum(len(tag) for tag in safe_tags)
        + max(0, len(safe_tags) - 1),
    )
    print(f"Category ID: {category_id}")
    print(f"Privacy: {PRIVACY_STATUS.upper()}")
    print("Public upload: DISABLED")
    print()

    if safe_tags:
        print("Sanitized tags:")
        for index, tag in enumerate(safe_tags, start=1):
            print(f"  {index:02d}. {tag}")
    else:
        print("Sanitized tags: NONE")

    print()

    # --------------------------------------------------------
    # Media upload
    # --------------------------------------------------------

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=8 * 1024 * 1024,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    # --------------------------------------------------------
    # Resumable upload
    # --------------------------------------------------------

    response = None

    try:
        while response is None:

            status, response = request.next_chunk()

            if status:
                progress = int(status.progress() * 100)

                print(
                    f"Upload progress: {progress}%",
                    end="\r",
                    flush=True,
                )

    except HttpError as exc:
        print()
        print()
        print("❌ YouTube API upload error")

        logger.error(
            "YouTube API error: %s",
            exc,
        )

        # Try to expose useful API error details.
        try:
            if hasattr(exc, "content") and exc.content:
                content = exc.content.decode(
                    "utf-8",
                    errors="replace",
                )

                print()
                print("YouTube API response:")
                print(content)

        except Exception:
            pass

        raise

    except Exception:
        print()
        raise

    print()
    print()
    print("✅ Video uploaded successfully.")

    # --------------------------------------------------------
    # Extract video ID
    # --------------------------------------------------------

    video_id = ""

    if isinstance(response, dict):
        video_id = str(
            response.get("id", "")
        ).strip()

    if not video_id:
        raise RuntimeError(
            "YouTube upload completed but no video ID was returned."
        )

    # --------------------------------------------------------
    # Verify privacy returned by API
    # --------------------------------------------------------

    returned_privacy = ""

    try:
        returned_privacy = str(
            response["status"]["privacyStatus"]
        ).strip().lower()
    except Exception:
        returned_privacy = ""

    if returned_privacy and returned_privacy != "unlisted":
        raise RuntimeError(
            "SAFETY STOP: YouTube returned privacy status "
            f"{returned_privacy!r}, expected 'unlisted'."
        )

    print(f"Video ID: {video_id}")
    print(f"Privacy verified: {returned_privacy or 'unlisted'}")
    print(
        f"YouTube URL: https://www.youtube.com/watch?v={video_id}"
    )

    return {
        "success": True,
        "video_id": video_id,
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "privacy_status": returned_privacy or PRIVACY_STATUS,
        "privacyStatus": returned_privacy or PRIVACY_STATUS,
        "title": title,
        "description": description,
        "tags": safe_tags,
        "category_id": category_id,
    }


# ============================================================
# PUBLIC FUNCTION USED BY main.py
# ============================================================

def upload_short_to_youtube(
    video_path: str | Path,
    title: str,
    description: str,
    tags=None,
):
    """
    Main uploader function used by main.py.

    Example:

        result = upload_short_to_youtube(
            video_path,
            title,
            description,
            tags=tags,
        )

    Privacy is ALWAYS UNLISTED.
    """

    print()
    print("🔐 Checking YouTube authentication...")

    youtube = get_authenticated_service()

    return upload_video(
        youtube=youtube,
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        category_id=get_category_id(),
    )


# ============================================================
# OPTIONAL SIMPLE TEST
# ============================================================

def test_authentication() -> None:
    """
    Test YouTube OAuth/API authentication without uploading.
    """

    print()
    print("=" * 70)
    print("🧪 YOUTUBE AUTHENTICATION TEST")
    print("=" * 70)

    youtube = get_authenticated_service()

    response = (
        youtube.channels()
        .list(
            part="snippet",
            mine=True,
        )
        .execute()
    )

    items = response.get("items", [])

    if not items:
        raise RuntimeError(
            "YouTube API authentication succeeded, "
            "but no channel was returned."
        )

    channel = items[0]

    channel_title = (
        channel.get("snippet", {})
        .get("title", "Unknown")
    )

    print()
    print("✅ YouTube authentication successful.")
    print(f"Channel: {channel_title}")


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    # This only tests authentication.
    # It does NOT upload a video.
    test_authentication()
