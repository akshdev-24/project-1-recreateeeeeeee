"""Gemini is used only to generate original Roman Hindi/Hinglish Shayari text."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google import genai

ROOT_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = ROOT_DIR / "content_history.json"
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

FALLBACK_SHAYARI = [
    "Kabhi khamoshi bhi bahut kuch keh jaati hai,\njo baat lafzon se na ho, woh aankhon mein reh jaati hai.",
    "Waqt badla, log badle, rishte bhi badal gaye,\nbas kuch yaadein thi jo dil mein wahi reh gaye.",
    "Jise dil se chaha, usse bhulana aasaan nahi,\nkuch log door hokar bhi kabhi anjaan nahi.",
    "Har muskurahat ke peeche ek kahani hoti hai,\nhar khamoshi mein bhi koi baat purani hoti hai.",
]


def get_client():
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable is missing.")
    return genai.Client(api_key=api_key)


def load_history() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
    except Exception:
        pass
    return []


def save_history(item: dict[str, Any]) -> None:
    history = load_history()
    history.append(item)
    HISTORY_FILE.write_text(json.dumps(history[-500:], ensure_ascii=False, indent=2), encoding="utf-8")


def generate_shayari() -> dict[str, str]:
    """Return only {'shayari': '...'}; no title, SEO, hashtags, queries or tags."""
    client = get_client()
    prompt = """
Write ONE original Roman Hindi/Hinglish shayari for a YouTube Short.
Rules:
- 4 to 8 short lines.
- Emotional, poetic and natural.
- Use Roman Hindi/Hinglish only; never Devanagari.
- No title.
- No hashtags.
- No keywords, SEO, queries, description, tags or explanations.
- Return JSON only in exactly this shape: {"shayari":"..."}
""".strip()
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = getattr(response, "text", "") or ""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
        shayari = str(data.get("shayari", "")).strip()
    except Exception:
        shayari = text
    if not shayari:
        raise RuntimeError("Gemini returned empty Shayari.")
    return {"shayari": shayari}


def local_fallback(history: list[dict[str, Any]] | None = None) -> dict[str, str]:
    used = {str(item.get("shayari", "")).strip() for item in (history or []) if isinstance(item, dict)}
    for text in FALLBACK_SHAYARI:
        if text not in used:
            return {"shayari": text}
    return {"shayari": FALLBACK_SHAYARI[0]}
