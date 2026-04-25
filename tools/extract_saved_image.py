#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import DB_PATH, DATA_DIR, SECRET
from backend.app.watermark import extract_payload_from_images

PATTERN = re.compile(r"^P([0-9a-fA-F]{8})A([0-9a-fA-F]{8})G([0-9a-fA-F]{4})$")


def main() -> None:
    p = argparse.ArgumentParser(description="Extract MVP payload from a saved watermarked image. Non-blind: needs original base image path.")
    p.add_argument("original", help="Original base image, e.g. data/pages/page_001/base.png")
    p.add_argument("watermarked", help="Saved leaked/downloaded watermarked image")
    p.add_argument("--seed", required=True, help="Seed stored in views.seed. For MVP debug only.")
    p.add_argument("--secret", default=os.environ.get("MANGA_TRACE_SECRET", SECRET))
    args = p.parse_args()

    result = extract_payload_from_images(args.original, args.watermarked, key=args.secret + ":" + args.seed)
    out = {"extract": result, "db_candidate": None}
    if result.get("text"):
        m = PATTERN.match(result["text"])
        if m:
            payload_id = int(m.group(1), 16)
            auth_tag = int(m.group(2), 16)
            with sqlite3.connect(DB_PATH) as con:
                con.row_factory = sqlite3.Row
                row = con.execute(
                    "SELECT * FROM views WHERE payload_id = ? AND auth_tag = ?",
                    (payload_id, auth_tag),
                ).fetchone()
                if row:
                    out["db_candidate"] = dict(row)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
