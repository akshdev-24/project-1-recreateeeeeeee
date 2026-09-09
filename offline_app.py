"""Offline Shayari Studio.
Run: python offline_app.py
No internet is required to type Shayari and create a video.
"""
from __future__ import annotations

import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from src.uploader import upload_short_to_youtube

from src.metadata_assets import load_metadata
from src.shayari_video import create_video

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)


def safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return text[:70] or "shayari"


def create_manual_video(text_widget: tk.Text, duration_var: tk.StringVar, status: tk.StringVar, upload: bool = False):
    text = text_widget.get("1.0", "end").strip()
    if not text or text == "Yahan apni Shayari likho…":
        messagebox.showwarning("Shayari missing", "Pehle apni Shayari likho.")
        return
    try:
        duration = int(duration_var.get())
        if duration < 5 or duration > 120:
            raise ValueError
    except ValueError:
        messagebox.showwarning("Invalid duration", "Duration 5–120 seconds ke beech rakho.")
        return

    try:
        title, description, tags, title_index = load_metadata()
        output = OUTPUT / f"{safe_filename(title)}_manual_short.mp4"
        status.set("Video ban rahi hai…")
        root.update_idletasks()
        create_video(text, str(output), duration)
        metadata = {
            "source": "manual_offline_screen",
            "shayari": text,
            "title": title,
            "description": description,
            "tags": tags,
            "title_asset_index": title_index + 1,
            "privacy_status": "unlisted",
            "font": "Times New Roman Regular",
        }
        output.with_suffix(".json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if upload:
            status.set("YouTube par UNLISTED upload ho raha hai…")
            root.update_idletasks()
            result = upload_short_to_youtube(
                str(output), title, description, tags=tags
            )
            privacy = str(result.get("privacy_status", result.get("privacyStatus", ""))).lower()
            if privacy and privacy != "unlisted":
                raise RuntimeError(f"Safety stop: upload privacy was {privacy}, not unlisted.")
            status.set("Uploaded successfully — UNLISTED")
            messagebox.showinfo("Done", f"Video upload ho gayi as UNLISTED.\n\nTitle: {title}")
        else:
            status.set(f"Ready: {output.name}")
            messagebox.showinfo("Done", f"Video create ho gayi:\n{output}")
    except Exception as exc:
        status.set("Error")
        messagebox.showerror("Error", str(exc))


def load_shayari_file(text_widget: tk.Text):
    path = filedialog.askopenfilename(
        title="Shayari text file select karo",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
    )
    if not path:
        return
    text = Path(path).read_text(encoding="utf-8-sig")
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", text)


def main():
    global root
    root = tk.Tk()
    root.title("Shayari Studio — Offline")
    root.geometry("780x650")
    root.minsize(650, 520)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="💔 SHAYARI STUDIO", font=("Times New Roman", 22)).pack(anchor="w")
    ttk.Label(frame, text="Offline Manual Video Creator", font=("Times New Roman", 12)).pack(anchor="w", pady=(0, 18))

    ttk.Label(frame, text="Apni Shayari:", font=("Times New Roman", 13)).pack(anchor="w")
    text = tk.Text(frame, wrap="word", font=("Times New Roman", 16), height=17)
    text.pack(fill="both", expand=True, pady=8)
    text.insert("1.0", "Yahan apni Shayari likho…")

    row = ttk.Frame(frame)
    row.pack(fill="x", pady=10)
    ttk.Label(row, text="Duration (sec):", font=("Times New Roman", 12)).pack(side="left")
    duration = tk.StringVar(value="15")
    ttk.Entry(row, textvariable=duration, width=8).pack(side="left", padx=8)
    ttk.Label(row, text="Metadata: assets/titles.txt + description.txt + tags.txt", font=("Times New Roman", 10)).pack(side="left", padx=12)

    status = tk.StringVar(value="Ready — internet ki zarurat nahi.")
    ttk.Label(frame, textvariable=status, font=("Times New Roman", 10)).pack(anchor="w", pady=8)
    button_row = ttk.Frame(frame)
    button_row.pack(fill="x", pady=(4, 0))
    ttk.Button(button_row, text="📄 LOAD SHAYARI .TXT", command=lambda: load_shayari_file(text)).pack(side="left", expand=True, fill="x", padx=(0, 6), ipady=8)
    ttk.Button(button_row, text="🎬 CREATE VIDEO", command=lambda: create_manual_video(text, duration, status, False)).pack(side="left", expand=True, fill="x", padx=6, ipady=8)
    ttk.Button(button_row, text="⬆ CREATE + UPLOAD UNLISTED", command=lambda: create_manual_video(text, duration, status, True)).pack(side="left", expand=True, fill="x", padx=(6, 0), ipady=8)
    ttk.Label(frame, text="Manual upload also stays UNLISTED. Internet is needed only for YouTube upload/OAuth.", font=("Times New Roman", 10)).pack(pady=(12, 0))
    root.mainloop()


if __name__ == "__main__":
    main()
