# ============================================================
# FILE: src/shayari_video.py
# ============================================================
#
# HINGLISH / ROMAN HINDI SHAYARI SHORTS VIDEO GENERATOR
#
# OUTPUT:
#   1080x1920
#   9:16
#
# VIDEO:
#   User background image/video
#   User background music
#   Static Roman Hindi Shayari
#
# NO:
#   - TTS
#   - voice
#   - text animation
#   - cream card
#   - paper overlay
#   - logo
#   - @handle
#   - footer
#   - extra UI
#
# ============================================================

from __future__ import annotations

import os
import random
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance


# ============================================================
# CONFIG
# ============================================================

WIDTH = 1080
HEIGHT = 1920
FPS = 30

DEFAULT_DURATION = int(
    os.getenv("SHAYARI_DURATION", "15")
)

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
}


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = ROOT_DIR / "assets"

MUSIC_DIR = ASSETS_DIR / "music"

FONTS_DIR = ASSETS_DIR / "fonts"


# ============================================================
# FONT SEARCH — TIMES NEW ROMAN REGULAR ONLY
# ============================================================

def get_body_font(size: int):
    """Load only Times New Roman Regular. No other font is permitted."""
    candidates = [
        FONTS_DIR / "times.ttf",
        FONTS_DIR / "Times New Roman.ttf",
        FONTS_DIR / "timesnewroman.ttf",
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)

    raise FileNotFoundError(
        "Times New Roman Regular font missing. Add the regular font as "
        "assets/fonts/times.ttf (or Times New Roman.ttf). No substitute font is allowed."
    )


# ============================================================
# BACKGROUND DISCOVERY
# ============================================================

def find_background() -> Path:

    preferred_names = [
        "background.jpg",
        "background.jpeg",
        "background.png",
        "background.webp",
        "bg.jpg",
        "bg.jpeg",
        "bg.png",
        "bg.webp",
        "background.mp4",
        "background.mov",
        "background.webm",
        "bg.mp4",
        "bg.mov",
        "bg.webm",
    ]

    for name in preferred_names:

        path = ASSETS_DIR / name

        if path.exists():

            return path

    candidates = []

    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue

        if path.name.lower() == "fallback.jpg":
            continue

        if path.suffix.lower() in (
            VIDEO_EXTENSIONS
            | IMAGE_EXTENSIONS
        ):

            candidates.append(path)

    if not candidates:

        fallback = ASSETS_DIR / "fallback.jpg"

        if fallback.exists():
            return fallback

        raise FileNotFoundError(
            "No background image/video found in assets/"
        )

    return random.choice(candidates)


# ============================================================
# MUSIC DISCOVERY
# ============================================================

def find_music() -> Path:

    preferred = [
        "bg_music.mp3",
        "background.mp3",
        "music.mp3",
        "bg_music.wav",
    ]

    for name in preferred:

        path = MUSIC_DIR / name

        if path.exists():
            return path

    candidates = [
        p
        for p in MUSIC_DIR.rglob("*")
        if p.is_file()
        and p.suffix.lower() in AUDIO_EXTENSIONS
    ]

    if not candidates:

        raise FileNotFoundError(
            "No music file found in assets/music/"
        )

    return random.choice(candidates)


# ============================================================
# IMAGE PREPARATION
# ============================================================

def fit_background_without_crop(image: Image.Image) -> Image.Image:
    """Fit the complete source image inside 1080x1920 without cropping.

    A blurred, enlarged copy fills any unused area so decorative edges of the
    original asset are never cut off.
    """
    image = image.convert("RGB")
    scale = min(WIDTH / image.width, HEIGHT / image.height)
    new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    foreground = image.resize(new_size, Image.Resampling.LANCZOS)

    # Full-frame blurred backdrop; the original image remains completely visible.
    bg_scale = max(WIDTH / image.width, HEIGHT / image.height)
    bg_size = (max(1, int(image.width * bg_scale)), max(1, int(image.height * bg_scale)))
    backdrop = image.resize(bg_size, Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(18))
    left = max(0, (backdrop.width - WIDTH) // 2)
    top = max(0, (backdrop.height - HEIGHT) // 2)
    backdrop = backdrop.crop((left, top, left + WIDTH, top + HEIGHT))

    canvas = Image.new("RGB", (WIDTH, HEIGHT))
    canvas.paste(backdrop, (0, 0))
    x = (WIDTH - foreground.width) // 2
    y = (HEIGHT - foreground.height) // 2
    canvas.paste(foreground, (x, y))
    return canvas


# ============================================================
# BACKGROUND FILTER
# ============================================================

def apply_background_filter(
    image: Image.Image,
) -> Image.Image:

    image = ImageEnhance.Contrast(
        image
    ).enhance(1.06)

    image = ImageEnhance.Color(
        image
    ).enhance(0.88)

    image = ImageEnhance.Brightness(
        image
    ).enhance(0.94)

    # Very subtle blur to make text readable.
    image = image.filter(
        ImageFilter.GaussianBlur(0.15)
    )

    # Subtle vignette
    overlay = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(
        overlay,
        "RGBA",
    )

    # Edge darkening
    steps = 18

    for i in range(steps):

        alpha = int(
            2 + (i / steps) * 8
        )

        margin = int(
            i * 18
        )

        draw.rectangle(
            (
                margin,
                margin,
                WIDTH - margin,
                HEIGHT - margin,
            ),
            outline=(0, 0, 0, alpha),
            width=2,
        )

    return Image.alpha_composite(
        image.convert("RGBA"),
        overlay,
    ).convert("RGB")


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_shayari_text(text: str) -> str:

    if not text:
        return ""

    text = str(text)

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove markdown
    text = text.replace("**", "")
    text = text.replace("__", "")

    # Remove common labels accidentally returned by AI
    unwanted_prefixes = [
        "shayari:",
        "shayari -",
        "poem:",
        "text:",
    ]

    stripped = text.strip()

    lower = stripped.lower()

    for prefix in unwanted_prefixes:

        if lower.startswith(prefix):

            stripped = stripped[
                len(prefix):
            ].strip()

            break

    # Absolutely no Devanagari.
    # If Gemini accidentally outputs it,
    # remove those characters.
    cleaned_chars = []

    for char in stripped:

        code = ord(char)

        # Devanagari Unicode block
        if 0x0900 <= code <= 0x097F:
            continue

        cleaned_chars.append(char)

    stripped = "".join(
        cleaned_chars
    )

    # Remove excessive spaces
    lines = []

    for line in stripped.split("\n"):

        line = " ".join(
            line.strip().split()
        )

        if line:
            lines.append(line)
        else:
            # preserve stanza breaks
            if lines and lines[-1] != "":
                lines.append("")

    # Avoid too many blank lines
    result = []

    previous_blank = False

    for line in lines:

        if not line:

            if not previous_blank:
                result.append("")

            previous_blank = True

        else:

            result.append(line)
            previous_blank = False

    return "\n".join(result).strip()


# ============================================================
# TEXT WRAPPING
# ============================================================

def text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
) -> float:

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    return bbox[2] - bbox[0]


def wrap_line(
    draw: ImageDraw.ImageDraw,
    line: str,
    font,
    max_width: int,
) -> list[str]:

    words = line.split()

    if not words:
        return [""]

    result = []

    current = words[0]

    for word in words[1:]:

        candidate = (
            current + " " + word
        )

        if (
            text_width(
                draw,
                candidate,
                font,
            )
            <= max_width
        ):

            current = candidate

        else:

            result.append(current)
            current = word

    result.append(current)

    return result


def prepare_text_lines(
    image: Image.Image,
    text: str,
    font,
    max_width: int,
) -> list[str]:

    draw = ImageDraw.Draw(image)

    final_lines = []

    for original_line in text.split("\n"):

        if not original_line.strip():

            final_lines.append("")
            continue

        wrapped = wrap_line(
            draw,
            original_line,
            font,
            max_width,
        )

        final_lines.extend(
            wrapped
        )

    return final_lines


# ============================================================
# TEXT POSITION
# ============================================================

def calculate_text_start_y(
    lines: list[str],
    font,
    area_top: int,
    area_bottom: int,
    line_gap: int,
    stanza_gap: int,
) -> int:

    # Calculate approximate block height.
    total_height = 0

    for line in lines:

        if line == "":

            total_height += stanza_gap

        else:

            bbox = font.getbbox(line)

            line_height = (
                bbox[3] - bbox[1]
            )

            total_height += (
                line_height + line_gap
            )

    available_height = (
        area_bottom - area_top
    )

    # Center vertically in allowed area
    y = area_top + (
        available_height
        - total_height
    ) // 2

    # Safety boundaries
    y = max(
        area_top,
        min(
            y,
            area_bottom - total_height,
        ),
    )

    return y


# ============================================================
# RENDER SHAYARI FRAME
# ============================================================

def render_shayari_frame(
    text: str,
    output_path: Path,
) -> None:

    # --------------------------------------------------------
    # Base image
    # --------------------------------------------------------

    background = find_background()

    print(
        f"Using background: {background}"
    )

    if (
        background.suffix.lower()
        in IMAGE_EXTENSIONS
    ):

        image = Image.open(
            background
        )

        image = fit_background_without_crop(
            image
        )

        image = apply_background_filter(
            image
        )

    else:

        # For video backgrounds, extract
        # first frame as the text reference.
        temp_frame = (
            Path(tempfile.gettempdir())
            / "shayari_background_frame.jpg"
        )

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            "0",
            "-i",
            str(background),
            "-frames:v",
            "1",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920",
            str(temp_frame),
        ]

        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        image = Image.open(
            temp_frame
        )

        image = fit_background_without_crop(
            image
        )

        image = apply_background_filter(
            image
        )

    # --------------------------------------------------------
    # Text
    # --------------------------------------------------------

    text = clean_shayari_text(
        text
    )

    if not text:

        raise ValueError(
            "Shayari text is empty."
        )

    # Shayari typography: Times New Roman Regular only.
    # Preserve the user's stanza/line structure and adapt size so the complete
    # poem fits cleanly without touching the decorative edges of the image.
    max_text_width = 700
    area_top = 320
    area_bottom = 1420
    line_gap = 20
    stanza_gap = 52

    font = None
    lines = []
    for font_size in range(68, 39, -2):
        candidate_font = get_body_font(font_size)
        candidate_lines = prepare_text_lines(
            image, text, candidate_font, max_text_width
        )
        total_height = 0
        for line in candidate_lines:
            if line == "":
                total_height += stanza_gap
            else:
                box = candidate_font.getbbox(line)
                total_height += (box[3] - box[1]) + line_gap
        if total_height <= (area_bottom - area_top):
            font = candidate_font
            lines = candidate_lines
            break

    if font is None:
        font = get_body_font(40)
        lines = prepare_text_lines(image, text, font, max_text_width)

    # --------------------------------------------------------
    # Text layer
    # --------------------------------------------------------

    text_layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(
        text_layer
    )

    # Main poetry area — centered and stanza-aware.

    y = calculate_text_start_y(
        lines,
        font,
        area_top,
        area_bottom,
        line_gap,
        stanza_gap,
    )

    # Black text to match the requested
    # reference-style typography.
    text_fill = (
        15,
        12,
        10,
        255,
    )

    for line in lines:

        if line == "":

            y += stanza_gap
            continue

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font,
        )

        line_width = (
            bbox[2] - bbox[0]
        )

        x = (
            WIDTH - line_width
        ) // 2

        draw.text(
            (
                x,
                y,
            ),
            line,
            font=font,
            fill=text_fill,
        )

        line_height = (
            bbox[3] - bbox[1]
        )

        y += (
            line_height
            + line_gap
        )

    # --------------------------------------------------------
    # Composite
    # --------------------------------------------------------

    final_image = Image.alpha_composite(
        image.convert("RGBA"),
        text_layer,
    )

    final_image.convert(
        "RGB"
    ).save(
        output_path,
        "JPEG",
        quality=95,
        optimize=True,
    )


# ============================================================
# FFMPEG HELPERS
# ============================================================

def run_ffmpeg(
    command: list[str],
) -> None:

    print(
        "Running FFmpeg..."
    )

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if process.returncode != 0:

        print(
            process.stderr[-5000:]
        )

        raise RuntimeError(
            "FFmpeg failed."
        )


# ============================================================
# CREATE IMAGE BACKGROUND VIDEO
# ============================================================

def create_image_background_video(
    background_image: Path,
    output_video: Path,
    duration: int,
) -> None:

    command = [
        "ffmpeg",
        "-y",

        "-loop",
        "1",

        "-i",
        str(background_image),

        "-t",
        str(duration),

        "-vf",
        (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "format=yuv420p"
        ),

        "-r",
        str(FPS),

        "-c:v",
        "libx264",

        "-preset",
        "medium",

        "-crf",
        "20",

        "-pix_fmt",
        "yuv420p",

        "-an",

        str(output_video),
    ]

    run_ffmpeg(
        command
    )


# ============================================================
# CREATE VIDEO BACKGROUND
# ============================================================

def create_video_background_video(
    background_video: Path,
    output_video: Path,
    duration: int,
) -> None:

    command = [
        "ffmpeg",
        "-y",

        "-stream_loop",
        "-1",

        "-i",
        str(background_video),

        "-t",
        str(duration),

        "-vf",
        (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "format=yuv420p"
        ),

        "-r",
        str(FPS),

        "-an",

        "-c:v",
        "libx264",

        "-preset",
        "medium",

        "-crf",
        "20",

        "-pix_fmt",
        "yuv420p",

        str(output_video),
    ]

    run_ffmpeg(
        command
    )


# ============================================================
# ADD MUSIC
# ============================================================

def add_music(
    silent_video: Path,
    music: Path,
    output_video: Path,
    duration: int,
) -> None:

    command = [
        "ffmpeg",
        "-y",

        "-i",
        str(silent_video),

        "-stream_loop",
        "-1",

        "-i",
        str(music),

        "-t",
        str(duration),

        "-map",
        "0:v:0",

        "-map",
        "1:a:0",

        "-c:v",
        "copy",

        "-c:a",
        "aac",

        "-b:a",
        "192k",

        "-af",
        "volume=0.65",

        "-shortest",

        "-movflags",
        "+faststart",

        str(output_video),
    ]

    run_ffmpeg(
        command
    )


# ============================================================
# CREATE VIDEO
# ============================================================

def create_video(
    text: str,
    output_path: str,
    duration: Optional[int] = None,
) -> str:

    duration = (
        duration
        or DEFAULT_DURATION
    )

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("")
    print("=" * 60)
    print("SHAYARI VIDEO GENERATOR")
    print("=" * 60)
    print("")
    print(
        f"Resolution: {WIDTH}x{HEIGHT}"
    )
    print(
        f"Duration: {duration}s"
    )
    print(
        "TTS: DISABLED"
    )
    print(
        "Text animation: DISABLED"
    )
    print(
        "Card overlay: DISABLED"
    )
    print(
        "Logo/handle: DISABLED"
    )
    print("")

    with tempfile.TemporaryDirectory() as temp:

        temp_dir = Path(temp)

        text_frame = (
            temp_dir
            / "shayari_frame.jpg"
        )

        silent_video = (
            temp_dir
            / "silent_video.mp4"
        )

        render_shayari_frame(
            text,
            text_frame,
        )

        background = find_background()

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # If background is an image:
        #   rendered frame becomes full video.
        #
        # If background is a video:
        #   create moving background first,
        #   then overlay static text frame.
        # ----------------------------------------------------

        if (
            background.suffix.lower()
            in IMAGE_EXTENSIONS
        ):

            create_image_background_video(
                text_frame,
                silent_video,
                duration,
            )

        else:

            background_video = (
                temp_dir
                / "background_video.mp4"
            )

            create_video_background_video(
                background,
                background_video,
                duration,
            )

            # Overlay text frame over moving video.
            command = [
                "ffmpeg",
                "-y",

                "-i",
                str(background_video),

                "-loop",
                "1",

                "-i",
                str(text_frame),

                "-filter_complex",
                (
                    "[1:v]format=rgba[text];"
                    "[0:v][text]overlay=0:0:format=auto,"
                    "format=yuv420p"
                ),

                "-t",
                str(duration),

                "-r",
                str(FPS),

                "-c:v",
                "libx264",

                "-preset",
                "medium",

                "-crf",
                "20",

                "-pix_fmt",
                "yuv420p",

                "-an",

                str(silent_video),
            ]

            run_ffmpeg(
                command
            )

        music = find_music()

        print(
            f"Using music: {music}"
        )

        add_music(
            silent_video,
            music,
            output,
            duration,
        )

    if not output.exists():

        raise RuntimeError(
            "Final video was not created."
        )

    print("")
    print(
        f"Video created: {output}"
    )

    return str(output)


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

def generate_video(
    text: str,
    output_path: str,
    duration: Optional[int] = None,
) -> str:

    return create_video(
        text,
        output_path,
        duration,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_output = (
        ROOT_DIR
        / "output"
        / "test_shayari.mp4"
    )

    create_video(
        """
Kabhi kabhi kisi ko paana
mohabbat nahi hoti...

Uske bina bhi
use chahte rehna,

shayad isi ko
sachhi mohabbat kehte hain.
""",
        str(test_output),
        15,
    )
