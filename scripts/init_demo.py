from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import DB_PATH, DATA_DIR
from backend.app.db import init_db
from backend.app.security import hash_password


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_demo_page(path: Path, page_number: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = 900, 1280
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    # manga-ish panels
    d.rectangle([40, 40, w - 40, 380], outline="black", width=5)
    d.rectangle([40, 420, 430, 820], outline="black", width=5)
    d.rectangle([470, 420, w - 40, 820], outline="black", width=5)
    d.rectangle([40, 860, w - 40, h - 40], outline="black", width=5)
    # halftone-ish background
    for y in range(60, 360, 18):
        for x in range(60, w - 60, 18):
            if (x + y + page_number * 7) % 36 == 0:
                d.ellipse([x, y, x + 4, y + 4], fill=(180, 180, 180))
    # characters / speech bubbles
    d.ellipse([120, 115, 260, 255], outline="black", width=4)
    d.rectangle([160, 255, 225, 350], outline="black", width=4)
    d.ellipse([560, 100, 790, 210], outline="black", width=4)
    d.text((600, 135), f"PAGE {page_number}", fill="black")
    d.line([95, 930, 805, 1190], fill=(100, 100, 100), width=3)
    d.line([805, 930, 95, 1190], fill=(100, 100, 100), width=3)
    d.text((75, 875), "Demo manga base image. This file is never served directly.", fill=(30, 30, 30))
    im.save(path)


def main() -> None:
    init_db()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            INSERT OR REPLACE INTO users(id, email, display_name, password_hash, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("user_demo", "demo@example.com", "Demo User", hash_password("password"), "active", now_iso()),
        )
        for n in (1, 2):
            rel = f"pages/page_{n:03d}/base.png"
            abs_path = DATA_DIR / rel
            make_demo_page(abs_path, n)
            con.execute(
                """
                INSERT OR REPLACE INTO pages(id, title, page_number, width, height, base_image_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (f"page_{n:03d}", "Demo Manga", n, 900, 1280, rel, now_iso()),
            )
        con.commit()
    print("Initialized demo DB")
    print("Login: demo@example.com / password")
    print(f"DB: {DB_PATH}")


if __name__ == "__main__":
    main()
