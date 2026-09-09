"""Compatibility wrapper for the single approved video renderer.

The active pipeline is src.shayari_video. This module intentionally does not
contain a second typography or SEO pipeline, so Times New Roman Regular remains
the only video font.
"""
from __future__ import annotations

from src.shayari_video import create_video, generate_video

__all__ = ["create_video", "generate_video"]
