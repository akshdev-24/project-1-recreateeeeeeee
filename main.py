from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import src.shayari_generator as shayari_generator
from src.metadata_assets import load_metadata
from src.shayari_video import create_video
from src.uploader import upload_short_to_youtube

ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("shayari-automation")

VIDEO_DURATION = int(os.getenv("SHAYARI_DURATION", "15"))
YOUTUBE_UPLOAD = os.getenv("YOUTUBE_UPLOAD", "true").lower() == "true"
MANUAL_SHAYARI = os.getenv("SHAYARI_INPUT", "").strip()


def validate_shayari(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        raise ValueError("Shayari is empty.")
    if re.search(r"[\u0900-\u097F]", text):
        raise ValueError("Use Roman Hindi/Hinglish text, not Devanagari.")
    return text


def build_content(shayari: str, source: str, model: str = "not_used") -> dict:
    shayari = validate_shayari(shayari)
    title, description, tags, title_index = load_metadata()
    return {
        "shayari": shayari,
        "title": title,
        "description": description,
        "tags": tags,
        "queries": [],
        "hashtags": [],
        "_title_asset_index": title_index + 1,
        "_metadata_source": "local_assets",
        "_source": source,
        "_gemini_model": model,
    }


def generate_content() -> dict:
    # Manual mode: Gemini is not called at all.
    if MANUAL_SHAYARI:
        logger.info("Manual Shayari supplied; Gemini skipped.")
        return build_content(MANUAL_SHAYARI, "manual")

    # Automatic mode: Gemini generates ONLY the Shayari text.
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is missing. Add it to GitHub Secrets for automatic mode.")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    shayari_generator.MODEL = model
    logger.info("Generating Shayari only with Gemini model: %s", model)

    result = shayari_generator.generate_shayari()
    if not isinstance(result, dict):
        raise RuntimeError("Gemini generator returned an invalid response.")
    return build_content(result.get("shayari", ""), "gemini", model)


def safe_filename(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", str(text or "shayari"))
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:70] or "shayari"


def save_json(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_video_file(content: dict) -> Path:
    output_path = OUTPUT_DIR / f"{safe_filename(content['title'])}_short.mp4"
    # Remove stale same-title output so artifact selection is deterministic.
    if output_path.exists():
        output_path.unlink()
    logger.info("Generating 1080x1920 video: %s", output_path)
    result = create_video(content["shayari"], str(output_path), VIDEO_DURATION)
    result_path = Path(result)
    if not result_path.exists():
        raise RuntimeError("Video generator reported success but output file is missing.")
    return result_path


def save_metadata(content: dict, video_path: Path) -> Path:
    path = video_path.with_suffix(".json")
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video": {"filename": video_path.name, "duration": VIDEO_DURATION, "width": 1080, "height": 1920, "aspect_ratio": "9:16"},
        "content": {
            "shayari": content.get("shayari", ""),
            "title": content.get("title", ""),
            "description": content.get("description", ""),
            "tags": content.get("tags", []),
            "queries": [],
            "hashtags": [],
        },
        "source": content.get("_source"),
        "gemini_model": content.get("_gemini_model"),
        "metadata_source": "assets/titles.txt + assets/description.txt + assets/tags.txt",
        "youtube_privacy": "unlisted",
    }
    save_json(payload, path)
    return path


def run() -> None:
    content = generate_content()
    logger.info("Selected title from local 50-title rotation: %s", content["title"])
    logger.info("Description/tags source: local assets only")
    logger.info("Generating Shayari video...")

    video_path = generate_video_file(content)
    metadata_path = save_metadata(content, video_path)
    logger.info("Video created: %s", video_path)
    logger.info("Metadata saved: %s", metadata_path)

    if YOUTUBE_UPLOAD:
        logger.info("Uploading to YouTube with privacy hard-coded to UNLISTED...")
        upload_result = upload_short_to_youtube(
            video_path=str(video_path),
            title=content["title"],
            description=content["description"],
            tags=content["tags"],
        )
        logger.info("YouTube upload complete: %s", upload_result.get("video_url", ""))
        logger.info("Privacy confirmed: %s", upload_result.get("privacy_status", ""))


if __name__ == "__main__":
    run()
