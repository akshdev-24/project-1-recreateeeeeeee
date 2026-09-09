# ============================================================
# FILE: src/uploader.py
# ============================================================
#
# YOUTUBE SHAYARI SHORTS UPLOADER
#
# IMPORTANT:
#   Videos are uploaded as UNLISTED.
#
#   This script NEVER changes them to PUBLIC.
#
# OAuth:
#   client_secrets.json -> Google OAuth application
#   credentials.json    -> authorized YouTube account token
#
# ============================================================

import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from google_auth_oauthlib.flow import InstalledAppFlow

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from googleapiclient.http import (
    MediaFileUpload
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parent.parent

CLIENT_SECRETS_FILE = (
    BASE_DIR
    / "client_secrets.json"
)

CREDENTIALS_FILE = (
    BASE_DIR
    / "credentials.json"
)


# ============================================================
# YOUTUBE CONFIG
# ============================================================

YOUTUBE_API_SERVICE_NAME = "youtube"

YOUTUBE_API_VERSION = "v3"

YOUTUBE_UPLOAD_SCOPE = [
    "https://www.googleapis.com/auth/youtube.upload"
]


# ============================================================
# PRIVACY
# ============================================================

# VERY IMPORTANT:
#
# User requested manual publishing.
#
# Therefore this is HARD-CODED to unlisted.
#
# Do NOT change this to public.
# ============================================================

PRIVACY_STATUS = "unlisted"


# ============================================================
# CATEGORY
# ============================================================

# 22 = People & Blogs
#
# We keep this configurable but default to 22.
#
YOUTUBE_CATEGORY_ID = os.getenv(
    "YOUTUBE_CATEGORY_ID",
    "22"
)


# ============================================================
# RETRY CONFIG
# ============================================================

MAX_UPLOAD_RETRIES = int(
    os.getenv(
        "YOUTUBE_UPLOAD_RETRIES",
        "5"
    )
)

RETRY_BASE_SECONDS = int(
    os.getenv(
        "YOUTUBE_RETRY_BASE",
        "5"
    )
)


# ============================================================
# APPLICATION NAME
# ============================================================

APPLICATION_NAME = (
    "Hinglish Shayari Shorts Automation"
)


# ============================================================
# VALIDATION
# ============================================================

def validate_files():
    """
    Validate OAuth files before starting.
    """

    print()
    print(
        "🔐 Checking YouTube OAuth files..."
    )

    # --------------------------------------------------------
    # client_secrets.json
    # --------------------------------------------------------

    if not CLIENT_SECRETS_FILE.exists():

        raise FileNotFoundError(
            "\nclient_secrets.json not found.\n\n"
            "Expected location:\n"
            f"{CLIENT_SECRETS_FILE}\n\n"
            "Create/download your OAuth client JSON "
            "from Google Cloud Console."
        )

    print(
        "✅ client_secrets.json found"
    )

    # --------------------------------------------------------
    # credentials.json
    #
    # It may not exist on first run.
    # The OAuth flow will create it.
    # --------------------------------------------------------

    if CREDENTIALS_FILE.exists():

        print(
            "✅ credentials.json found"
        )

    else:

        print(
            "ℹ️ credentials.json not found."
        )

        print(
            "   First upload will start OAuth authorization."
        )


# ============================================================
# LOAD CREDENTIALS
# ============================================================

def get_credentials() -> Credentials:
    """
    Load saved credentials.

    If credentials are expired but have a refresh token,
    refresh automatically.

    If no credentials exist, start browser OAuth.
    """

    credentials = None

    # --------------------------------------------------------
    # Existing credentials
    # --------------------------------------------------------

    if CREDENTIALS_FILE.exists():

        print(
            "🔑 Loading saved YouTube credentials..."
        )

        try:

            credentials = Credentials.from_authorized_user_file(
                str(CREDENTIALS_FILE),
                YOUTUBE_UPLOAD_SCOPE
            )

        except Exception as error:

            print(
                "⚠️ Existing credentials.json could not "
                "be loaded."
            )

            print(
                f"   Error: {error}"
            )

            credentials = None

    # ========================================================
    # Refresh existing token
    # ========================================================

    if credentials:

        if credentials.valid:

            print(
                "✅ YouTube credentials are valid."
            )

        elif (
            credentials.expired
            and credentials.refresh_token
        ):

            print(
                "🔄 Access token expired."
            )

            print(
                "   Refreshing token..."
            )

            try:

                credentials.refresh(
                    Request()
                )

                print(
                    "✅ Token refreshed."
                )

                save_credentials(
                    credentials
                )

            except Exception as error:

                print(
                    "⚠️ Token refresh failed:"
                )

                print(
                    error
                )

                credentials = None

        else:

            print(
                "⚠️ Saved credentials are invalid."
            )

            credentials = None

    # ========================================================
    # OAuth browser flow
    # ========================================================

    if not credentials:

        print()
        print(
            "=" * 60
        )

        print(
            "YOUTUBE OAUTH AUTHORIZATION REQUIRED"
        )

        print(
            "=" * 60
        )

        print()

        print(
            "A browser window will open."
        )

        print(
            "Sign in using the Google account "
            "that owns the YouTube channel."
        )

        print()

        print(
            "IMPORTANT:"
        )

        print(
            "Choose the SAME YouTube channel/account "
            "you want this automation to upload to."
        )

        print()

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRETS_FILE),
            YOUTUBE_UPLOAD_SCOPE
        )

        credentials = flow.run_local_server(
            port=0,

            access_type="offline",

            prompt="consent"
        )

        print()
        print(
            "✅ OAuth authorization completed."
        )

        save_credentials(
            credentials
        )

    return credentials


# ============================================================
# SAVE CREDENTIALS
# ============================================================

def save_credentials(
    credentials: Credentials
):
    """
    Save OAuth credentials to credentials.json.
    """

    try:

        CREDENTIALS_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8"
        )

        print(
            f"💾 credentials saved:"
        )

        print(
            f"   {CREDENTIALS_FILE}"
        )

    except Exception as error:

        raise RuntimeError(
            "Could not save credentials.json: "
            f"{error}"
        )


# ============================================================
# BUILD YOUTUBE CLIENT
# ============================================================

def get_authenticated_service():
    """
    Create authenticated YouTube API client.
    """

    validate_files()

    credentials = get_credentials()

    youtube = build(
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        credentials=credentials,
        cache_discovery=False
    )

    print(
        "✅ YouTube API client initialized."
    )

    return youtube


# ============================================================
# CLEAN TAGS
# ============================================================

def clean_tags(
    tags: Optional[List[str]]
) -> List[str]:
    """
    Clean tags before sending to YouTube.
    """

    if not tags:
        return []

    cleaned = []

    seen = set()

    for tag in tags:

        if tag is None:
            continue

        tag = str(
            tag
        ).strip()

        if not tag:
            continue

        # ----------------------------------------------------
        # YouTube tag character cleanup.
        # ----------------------------------------------------

        tag = tag.replace(
            "\n",
            " "
        )

        tag = tag.replace(
            "\r",
            " "
        )

        tag = " ".join(
            tag.split()
        )

        if not tag:
            continue

        key = tag.lower()

        if key in seen:
            continue

        seen.add(
            key
        )

        cleaned.append(
            tag
        )

    return cleaned


# ============================================================
# CLEAN TITLE
# ============================================================

def clean_title(
    title: str
) -> str:

    title = str(
        title or ""
    ).strip()

    title = " ".join(
        title.split()
    )

    if not title:

        title = (
            "Heart Touching Shayari "
            "| Hinglish Shayari #Shorts"
        )

    # --------------------------------------------------------
    # Keep title within YouTube's practical title length.
    # --------------------------------------------------------

    return title[:100]


# ============================================================
# CLEAN DESCRIPTION
# ============================================================

def clean_description(
    description: str
) -> str:

    description = str(
        description or ""
    ).strip()

    if not description:

        description = (
            "Heart touching Hinglish Shayari "
            "for everyone who feels deeply.\n\n"
            "Hinglish Shayari | Hindi Shayari | "
            "Love Shayari | Sad Shayari | "
            "Heart Touching Shayari\n\n"
            "#shayari #hindishayari #hinglishshayari "
            "#loveshayari #sadshayari #shorts"
        )

    return description


# ============================================================
# UPLOAD VIDEO
# ============================================================

def upload_video(
    youtube,
    video_path: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    thumbnail_path: Optional[str] = None,
):
    """
    Upload video to YouTube as UNLISTED.
    """

    video_file = Path(
        video_path
    )

    if not video_file.exists():

        raise FileNotFoundError(
            f"Video file not found: "
            f"{video_file}"
        )

    if not video_file.is_file():

        raise ValueError(
            f"Video path is not a file: "
            f"{video_file}"
        )

    # --------------------------------------------------------
    # Metadata cleanup
    # --------------------------------------------------------

    title = clean_title(
        title
    )

    description = clean_description(
        description
    )

    tags = clean_tags(
        tags
    )

    # ========================================================
    # IMPORTANT SECURITY CHECK
    # ========================================================

    # Privacy is intentionally hard-coded.
    #
    # This prevents accidental PUBLIC uploads.
    #
    privacy_status = "unlisted"

    # ========================================================
    # REQUEST BODY
    # ========================================================

    body = {
        "snippet": {
            "title": title,

            "description": description,

            "categoryId": YOUTUBE_CATEGORY_ID,

            "tags": tags,

            "defaultLanguage": "en",

            "defaultAudioLanguage": "hi",
        },

        "status": {

            "privacyStatus": privacy_status,

            "selfDeclaredMadeForKids": False,

            "embeddable": True,

            "publicStatsViewable": True,

            # ------------------------------------------------
            # We don't mark this as synthetic media here
            # automatically because that disclosure should
            # depend on the actual content.
            # ------------------------------------------------
        }
    }

    # ========================================================
    # PRINT UPLOAD INFO
    # ========================================================

    print()
    print(
        "=" * 60
    )

    print(
        "📤 YOUTUBE UPLOAD"
    )

    print(
        "=" * 60
    )

    print(
        f"File: {video_file.name}"
    )

    print(
        f"Title: {title}"
    )

    print(
        f"Tags: {len(tags)}"
    )

    print(
        "Privacy: UNLISTED"
    )

    print(
        "Public upload: DISABLED"
    )

    print(
        "=" * 60
    )

    # ========================================================
    # MEDIA
    # ========================================================

    media = MediaFileUpload(
        str(video_file),

        mimetype="video/mp4",

        chunksize=8 * 1024 * 1024,

        resumable=True
    )

    # ========================================================
    # INSERT REQUEST
    # ========================================================

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    # ========================================================
    # RESUMABLE UPLOAD
    # ========================================================

    response = None

    retry_count = 0

    while response is None:

        try:

            print(
                "⬆️ Uploading..."
            )

            status, response = (
                request.next_chunk()
            )

            if status:

                progress = int(
                    status.progress()
                    * 100
                )

                print(
                    f"   Progress: {progress}%"
                )

        except HttpError as error:

            status_code = getattr(
                error.resp,
                "status",
                None
            )

            print()
            print(
                f"⚠️ YouTube API error: "
                f"{status_code}"
            )

            print(
                error
            )

            # ------------------------------------------------
            # Retry transient errors.
            # ------------------------------------------------

            if status_code in (
                500,
                502,
                503,
                504,
            ):

                retry_count += 1

                if (
                    retry_count
                    > MAX_UPLOAD_RETRIES
                ):

                    raise

                wait_seconds = (
                    RETRY_BASE_SECONDS
                    * (
                        2
                        ** (
                            retry_count - 1
                        )
                    )
                )

                print(
                    f"🔄 Retrying in "
                    f"{wait_seconds}s..."
                )

                time.sleep(
                    wait_seconds
                )

            else:

                raise

        except Exception as error:

            retry_count += 1

            print()
            print(
                "⚠️ Upload exception:"
            )

            print(
                error
            )

            if (
                retry_count
                > MAX_UPLOAD_RETRIES
            ):

                raise

            wait_seconds = (
                RETRY_BASE_SECONDS
                * (
                    2
                    ** (
                        retry_count - 1
                    )
                )
            )

            print(
                f"🔄 Retrying in "
                f"{wait_seconds}s..."
            )

            time.sleep(
                wait_seconds
            )

    # ========================================================
    # RESPONSE
    # ========================================================

    video_id = response.get(
        "id"
    )

    if not video_id:

        raise RuntimeError(
            "YouTube upload completed "
            "but no video ID was returned."
        )

    video_url = (
        f"https://www.youtube.com/watch?v="
        f"{video_id}"
    )

    shorts_url = (
        f"https://www.youtube.com/shorts/"
        f"{video_id}"
    )

    # ========================================================
    # FINAL SAFETY CHECK
    # ========================================================

    uploaded_privacy = (
        response
        .get(
            "status",
            {}
        )
        .get(
            "privacyStatus"
        )
    )

    print()
    print(
        "=" * 60
    )

    print(
        "✅ YOUTUBE UPLOAD COMPLETE"
    )

    print(
        "=" * 60
    )

    print(
        f"Video ID: {video_id}"
    )

    print(
        f"Privacy: {uploaded_privacy}"
    )

    print(
        f"URL: {video_url}"
    )

    print(
        f"Shorts URL: {shorts_url}"
    )

    # --------------------------------------------------------
    # Hard safety check.
    #
    # If YouTube ever returns anything unexpected,
    # don't silently continue.
    # --------------------------------------------------------

    if uploaded_privacy != "unlisted":

        raise RuntimeError(
            "SAFETY CHECK FAILED!\n"
            f"Expected: unlisted\n"
            f"Received: {uploaded_privacy}"
        )

    print(
        "🔒 Confirmed: video is UNLISTED."
    )

    print(
        "You can manually change it to "
        "PUBLIC from YouTube Studio."
    )

    print(
        "=" * 60
    )

    # ========================================================
    # OPTIONAL THUMBNAIL
    # ========================================================

    if thumbnail_path:

        thumbnail = Path(
            thumbnail_path
        )

        if thumbnail.exists():

            try:

                print(
                    "🖼️ Uploading thumbnail..."
                )

                youtube.thumbnails().set(
                    videoId=video_id,

                    media_body=MediaFileUpload(
                        str(thumbnail),

                        mimetype="image/jpeg"
                    )
                ).execute()

                print(
                    "✅ Thumbnail uploaded."
                )

            except Exception as error:

                print(
                    "⚠️ Thumbnail upload failed."
                )

                print(
                    error
                )

                # ------------------------------------------------
                # Thumbnail failure must NOT make the entire
                # video upload fail.
                # ------------------------------------------------

        else:

            print(
                "ℹ️ Thumbnail file not found."
            )

    return {
        "video_id": video_id,

        "video_url": video_url,

        "shorts_url": shorts_url,

        "privacy_status": uploaded_privacy,

        "title": title,
    }


# ============================================================
# MAIN COMPATIBILITY FUNCTION
# ============================================================

def upload_short_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    thumbnail_path: Optional[str] = None,
):
    """
    Compatibility function used by main.py.

    Example:

        upload_short_to_youtube(
            video_path="output/video.mp4",
            title="Heart Touching Shayari",
            description="...",
            tags=[
                "shayari",
                "hindi shayari",
                "hinglish shayari"
            ]
        )
    """

    youtube = get_authenticated_service()

    return upload_video(
        youtube=youtube,

        video_path=video_path,

        title=title,

        description=description,

        tags=tags,

        thumbnail_path=thumbnail_path,
    )


# ============================================================
# CHECK AUTHENTICATED CHANNEL
# ============================================================

def get_authenticated_channel():
    """
    Return the YouTube channel connected to credentials.json.

    Useful for verifying that you authorized the correct
    YouTube account/channel.
    """

    youtube = get_authenticated_service()

    response = (
        youtube.channels()
        .list(
            part="snippet,contentDetails,statistics",

            mine=True
        )
        .execute()
    )

    items = response.get(
        "items",
        []
    )

    if not items:

        raise RuntimeError(
            "No YouTube channel was found "
            "for the authenticated Google account."
        )

    channel = items[0]

    snippet = channel.get(
        "snippet",
        {}
    )

    return {
        "channel_id": channel.get(
            "id"
        ),

        "channel_title": snippet.get(
            "title"
        ),

        "custom_url": snippet.get(
            "customUrl"
        ),

        "subscriber_count": channel.get(
            "statistics",
            {}
        ).get(
            "subscriberCount"
        ),
    }


# ============================================================
# TEST AUTHENTICATION
# ============================================================

if __name__ == "__main__":

    print()
    print(
        "=" * 60
    )

    print(
        "YOUTUBE CHANNEL AUTH TEST"
    )

    print(
        "=" * 60
    )

    try:

        channel = (
            get_authenticated_channel()
        )

        print()
        print(
            "✅ AUTHENTICATION SUCCESSFUL"
        )

        print(
            f"Channel: "
            f"{channel['channel_title']}"
        )

        print(
            f"Channel ID: "
            f"{channel['channel_id']}"
        )

        if channel.get(
            "custom_url"
        ):

            print(
                f"Handle: "
                f"{channel['custom_url']}"
            )

        print()

        print(
            "Upload privacy is permanently:"
        )

        print(
            "UNLISTED"
        )

    except Exception as error:

        print()
        print(
            "❌ AUTHENTICATION FAILED"
        )

        print(
            error
        )

        sys.exit(1)
