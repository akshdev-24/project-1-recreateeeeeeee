"""Manual YouTube metadata assets and 50-title rotation."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
TITLE_STATE_FILE = ROOT_DIR / "title_rotation.json"


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Required asset missing: {path}")
    return path.read_text(encoding="utf-8-sig").strip()


def load_titles() -> list[str]:
    raw = _read_text(ASSETS_DIR / "titles.txt")
    titles = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(titles) != 50:
        raise ValueError(
            f"assets/titles.txt must contain exactly 50 non-empty titles; found {len(titles)}."
        )
    if len({t.casefold() for t in titles}) != 50:
        raise ValueError("assets/titles.txt contains duplicate titles. All 50 must be unique.")
    return titles


def load_description() -> str:
    return _read_text(ASSETS_DIR / "description.txt")


def load_tags() -> list[str]:
    raw = _read_text(ASSETS_DIR / "tags.txt")
    # Supports comma-separated or one-tag-per-line assets.
    tags = [x.strip() for x in re.split(r"[,\n|]+", raw) if x.strip()]
    result: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            result.append(tag)
    return result


def _load_state() -> dict[str, Any]:
    if not TITLE_STATE_FILE.exists():
        return {"used_titles": []}
    try:
        data = json.loads(TITLE_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("used_titles"), list):
            return data
    except Exception:
        pass
    return {"used_titles": []}


def _save_state(state: dict[str, Any]) -> None:
    TITLE_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def select_new_title() -> tuple[str, int]:
    """Return an unused title and its 0-based asset index.

    Titles are randomised within each 50-title cycle. No title repeats until
    all 50 have been used; then a fresh cycle starts.
    """
    titles = load_titles()
    state = _load_state()
    used = {int(i) for i in state.get("used_titles", []) if str(i).isdigit()}
    available = [i for i in range(50) if i not in used]

    if not available:
        used = set()
        available = list(range(50))

    index = random.choice(available)
    used.add(index)
    _save_state({"used_titles": sorted(used)})
    return titles[index], index


def load_metadata() -> tuple[str, str, list[str], int]:
    title, index = select_new_title()
    return title, load_description(), load_tags(), index
