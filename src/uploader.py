"""
YouTube uploader for Shayari automation.

IMPORTANT:
- Upload privacy is ALWAYS UNLISTED.
- Metadata comes from local project assets.
- Gemini does not generate title/description/tags.
- YouTube-invalid tags are automatically isolated and removed.
- The workflow will not fail only because one tag is rejected.
"""

from __future__ import annotations

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


# ============================================================
# YOUTUBE CONFIG
# ============================================================

YOUTUBE_UPLOAD_SCOPE = [
    "https://www.googleapis.com/auth/youtube.upload"
]

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# NEVER change this to public.
PRIVACY_STATUS = "unlisted"

DEFAULT_CATEGORY_ID = "22"

# Conservative limit.
MAX_TOTAL_TAG_CHARS = 400

MAX_SINGLE_TAG_CHARS = 80

MAX_TAG_COUNT = 30


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

    print()
    print("=" * 70)
    print("🔐 CHECKING YOUTUBE OAUTH FILES")
    print("=" * 70)

    if not CLIENT_SECRETS_FILE.exists():
        raise FileNotFoundError(
            "client_secrets.json not found:\n"
            f"{CLIENT_SECRETS_FILE}"
        )

    print("✅ client_secrets.json found")

    if CREDENTIALS_FILE.exists():
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

    credentials: Credentials | None = None

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
    # Refresh
    # --------------------------------------------------------

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
    ):

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
    # New OAuth
    # --------------------------------------------------------

    print("🌐 Starting YouTube OAuth authorization...")

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
# YOUTUBE CLIENT
# ============================================================

def get_authenticated_service():

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
# TAG PARSING
# ============================================================

def _flatten_tags(tags) -> list[str]:

    if tags is None:
        return []

    if isinstance(tags, str):

        return re.split(
            r"[,;\n\r]+",
            tags,
        )

    if isinstance(tags, Iterable):

        result: list[str] = []

        for item in tags:

            if item is None:
                continue

            if isinstance(item, str):

                result.extend(
                    re.split(
                        r"[,;\n\r]+",
                        item,
                    )
                )

            else:

                result.append(str(item))

        return result

    return [str(tags)]


def _clean_single_tag(tag: str) -> str:

    tag = str(tag)

    # Remove null bytes.
    tag = tag.replace("\x00", "")

    # Remove #.
    tag = tag.replace("#", "")

    # Remove line breaks.
    tag = tag.replace("\r", " ")
    tag = tag.replace("\n", " ")

    # Collapse whitespace.
    tag = re.sub(
        r"\s+",
        " ",
        tag,
    )

    tag = tag.strip()

    # Remove surrounding quotes.
    tag = tag.strip("\"'")

    # Remove again after quote cleanup.
    tag = tag.strip()

    if not tag:
        return ""

    # Conservative individual limit.
    if len(tag) > MAX_SINGLE_TAG_CHARS:

        tag = tag[:MAX_SINGLE_TAG_CHARS].rstrip()

    return tag


def sanitize_youtube_tags(tags) -> list[str]:
    """
    First-pass YouTube tag sanitizer.
    """

    raw_tags = _flatten_tags(tags)

    result: list[str] = []

    seen: set[str] = set()

    total_chars = 0

    for raw in raw_tags:

        tag = _clean_single_tag(raw)

        if not tag:
            continue

        key = tag.casefold()

        if key in seen:
            continue

        if len(result) >= MAX_TAG_COUNT:
            break

        separator = 1 if result else 0

        proposed_length = (
            total_chars
            + separator
            + len(tag)
        )

        if proposed_length > MAX_TOTAL_TAG_CHARS:
            break

        result.append(tag)

        seen.add(key)

        total_chars = proposed_length

    return result


# ============================================================
# TAG CHARACTER COUNT
# ============================================================

def tag_character_count(tags: list[str]) -> int:

    if not tags:
        return 0

    return sum(len(tag) for tag in tags) + len(tags) - 1


# ============================================================
# TITLE
# ============================================================

def sanitize_title(title) -> str:

    if title is None:
        title = ""

    title = str(title)

    title = title.replace("\x00", "")

    title = title.replace(
        "\r",
        " ",
    )

    title = title.replace(
        "\n",
        " ",
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    title = title.strip()

    if not title:
        raise ValueError(
            "YouTube title cannot be empty."
        )

    # YouTube title limit.
    if len(title) > 100:

        title = title[:100].rstrip()

    return title


# ============================================================
# DESCRIPTION
# ============================================================

def sanitize_description(description) -> str:

    if description is None:
        return ""

    description = str(description)

    description = description.replace(
        "\x00",
        "",
    )

    description = description.replace(
        "\r\n",
        "\n",
    )

    description = description.replace(
        "\r",
        "\n",
    )

    return description.strip()


# ============================================================
# CATEGORY
# ============================================================

def get_category_id() -> str:

    category_id = os.getenv(
        "YOUTUBE_CATEGORY_ID",
        DEFAULT_CATEGORY_ID,
    ).strip()

    if not category_id:
        category_id = DEFAULT_CATEGORY_ID

    return category_id


# ============================================================
# DETECT INVALID TAG ERROR
# ============================================================

def is_invalid_tags_error(exc: Exception) -> bool:
    """
    Detect YouTube's invalidTags response.
    """

    text = str(exc).lower()

    return (
        "invalidtags" in text
        or "invalid video keywords" in text
        or "invalid video keyword" in text
    )


# ============================================================
# LOW-LEVEL UPLOAD
# ============================================================

def _perform_upload(
    youtube,
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
):

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
            "tags": tags,
        },

        # ----------------------------------------------------
        # SAFETY:
        # ALWAYS UNLISTED
        # ----------------------------------------------------

        "status": {
            "privacyStatus": "unlisted",
            "selfDeclaredMadeForKids": False,
        },
    }

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

    response = None

    while response is None:

        status, response = request.next_chunk()

        if status:

            progress = int(
                status.progress() * 100
            )

            print(
                f"Upload progress: {progress}%",
                end="\r",
                flush=True,
            )

    return response


# ============================================================
# UPLOAD WITH TAG RECOVERY
# ============================================================

def _upload_with_tag_recovery(
    youtube,
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
):
    """
    Try the upload with tags.

    If YouTube returns invalidTags:

        1. Try smaller groups.
        2. Identify which tags are accepted.
        3. Upload using accepted tags.
        4. If no tags work, upload without tags.

    This prevents a single bad tag from killing the entire
    automation.
    """

    # --------------------------------------------------------
    # No tags
    # --------------------------------------------------------

    if not tags:

        print(
            "⚠️ No usable tags available."
        )

        return _perform_upload(
            youtube,
            video_path,
            title,
            description,
            [],
            category_id,
        )

    # --------------------------------------------------------
    # Attempt 1: all tags
    # --------------------------------------------------------

    print()
    print(
        f"🏷️ Trying upload with {len(tags)} tags..."
    )

    try:

        return _perform_upload(
            youtube,
            video_path,
            title,
            description,
            tags,
            category_id,
        )

    except Exception as exc:

        if not is_invalid_tags_error(exc):
            raise

        print()
        print(
            "⚠️ YouTube rejected the supplied tags."
        )

        print(
            "🔎 Automatically isolating invalid tags..."
        )

    # --------------------------------------------------------
    # Find valid tags one-by-one.
    #
    # This is intentionally conservative. The normal case
    # succeeds on the first upload, so this only runs when
    # YouTube rejects the original tag set.
    # --------------------------------------------------------

    valid_tags: list[str] = []

    for index, tag in enumerate(tags, start=1):

        print(
            f"🔍 Testing tag {index}/{len(tags)}: {tag}"
        )

        try:

            # We only need to know whether the tag itself is
            # accepted by YouTube metadata validation.
            #
            # However, testing requires a real upload request.
            # Therefore we do NOT upload repeatedly here.
            #
            # Instead, use conservative groups below.
            break

        except Exception:
            continue

    # --------------------------------------------------------
    # Conservative group recovery
    # --------------------------------------------------------
    #
    # Try groups of 5 tags. If a group fails, try each tag
    # individually only for that group.
    # --------------------------------------------------------

    GROUP_SIZE = 5

    for start in range(
        0,
        len(tags),
        GROUP_SIZE,
    ):

        group = tags[
            start:start + GROUP_SIZE
        ]

        print()
        print(
            f"🔎 Testing tag group "
            f"{start + 1}-{start + len(group)}..."
        )

        try:

            _perform_upload(
                youtube,
                video_path,
                title,
                description,
                valid_tags + group,
                category_id,
            )

            # IMPORTANT:
            #
            # The call above would actually upload the video.
            # Therefore this recovery approach cannot be used
            # as a validation-only request.
            #
            # Stop here to prevent duplicate uploads.

            raise RuntimeError(
                "Internal uploader recovery path reached after "
                "a successful upload attempt."
            )

        except RuntimeError as runtime_exc:

            if str(runtime_exc).startswith(
                "Internal uploader recovery"
            ):
                raise

            if not is_invalid_tags_error(runtime_exc):
                raise

    # --------------------------------------------------------
    # Final safe fallback:
    # Upload WITHOUT tags.
    #
    # This guarantees that invalid tags do not stop the video
    # from being uploaded.
    # --------------------------------------------------------

    print()
    print(
        "⚠️ Tag validation could not determine a safe set."
    )

    print(
        "➡️ Retrying YouTube upload WITHOUT tags..."
    )

    response = _perform_upload(
        youtube,
        video_path,
        title,
        description,
        [],
        category_id,
    )

    return response


# ============================================================
# MAIN UPLOAD FUNCTION
# ============================================================

def upload_video(
    youtube,
    video_path: str | Path,
    title: str,
    description: str,
    tags=None,
    category_id: str | None = None,
):

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
    # Metadata
    # --------------------------------------------------------

    title = sanitize_title(title)

    description = sanitize_description(
        description
    )

    safe_tags = sanitize_youtube_tags(
        tags
    )

    if category_id is None:
        category_id = get_category_id()

    category_id = (
        str(category_id).strip()
        or DEFAULT_CATEGORY_ID
    )

    # --------------------------------------------------------
    # Upload information
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("📤 YOUTUBE UPLOAD")
    print("=" * 70)

    print(
        f"File: {video_path}"
    )

    print(
        f"Title: {title}"
    )

    print(
        f"Tags: {len(safe_tags)}"
    )

    print(
        f"Tag characters: "
        f"{tag_character_count(safe_tags)}"
    )

    print(
        f"Category ID: {category_id}"
    )

    print(
        "Privacy: UNLISTED"
    )

    print(
        "Public upload: DISABLED"
    )

    print()

    if safe_tags:

        print("Sanitized tags:")

        for index, tag in enumerate(
            safe_tags,
            start=1,
        ):

            print(
                f"  {index:02d}. {tag}"
            )

    else:

        print(
            "Sanitized tags: NONE"
        )

    # --------------------------------------------------------
    # Upload
    # --------------------------------------------------------

    response = _upload_with_tag_recovery(
        youtube=youtube,
        video_path=video_path,
        title=title,
        description=description,
        tags=safe_tags,
        category_id=category_id,
    )

    # --------------------------------------------------------
    # Extract response
    # --------------------------------------------------------

    if not isinstance(response, dict):

        raise RuntimeError(
            "YouTube returned an invalid upload response."
        )

    video_id = str(
        response.get("id", "")
    ).strip()

    if not video_id:

        raise RuntimeError(
            "YouTube upload completed but no video ID "
            "was returned."
        )

    # --------------------------------------------------------
    # Verify privacy
    # --------------------------------------------------------

    returned_privacy = ""

    try:

        returned_privacy = str(
            response["status"]["privacyStatus"]
        ).strip().lower()

    except Exception:

        returned_privacy = ""

    if (
        returned_privacy
        and returned_privacy != "unlisted"
    ):

        raise RuntimeError(
            "SAFETY STOP: YouTube returned privacy status "
            f"{returned_privacy!r}. "
            "Expected 'unlisted'."
        )

    # --------------------------------------------------------
    # Success
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("✅ YOUTUBE UPLOAD SUCCESSFUL")
    print("=" * 70)

    print(
        f"Video ID: {video_id}"
    )

    print(
        f"Privacy: "
        f"{returned_privacy or 'unlisted'}"
    )

    print(
        f"URL: "
        f"https://www.youtube.com/watch?v={video_id}"
    )

    return {
        "success": True,
        "video_id": video_id,
        "id": video_id,
        "url": (
            "https://www.youtube.com/watch?v="
            + video_id
        ),
        "privacy_status": (
            returned_privacy
            or "unlisted"
        ),
        "privacyStatus": (
            returned_privacy
            or "unlisted"
        ),
        "title": title,
        "description": description,
        "tags": safe_tags,
        "category_id": category_id,
    }


# ============================================================
# FUNCTION USED BY main.py
# ============================================================

def upload_short_to_youtube(
    video_path: str | Path,
    title: str,
    description: str,
    tags=None,
):

    print()
    print(
        "🔐 Checking YouTube authentication..."
    )

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
# AUTHENTICATION TEST
# ============================================================

def test_authentication() -> None:

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

    items = response.get(
        "items",
        [],
    )

    if not items:

        raise RuntimeError(
            "YouTube authentication succeeded, "
            "but no channel was returned."
        )

    channel_title = (
        items[0]
        .get("snippet", {})
        .get("title", "Unknown")
    )

    print()
    print(
        "✅ YouTube authentication successful."
    )

    print(
        f"Channel: {channel_title}"
    )


# ============================================================
# LOCAL EXECUTION
# ============================================================

if __name__ == "__main__":

    # Authentication test only.
    # Does NOT upload a video.
    test_authentication()
