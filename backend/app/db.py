from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DB_PATH, DATA_DIR

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  display_name TEXT,
  password_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS pages (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  page_number INTEGER NOT NULL,
  width INTEGER,
  height INTEGER,
  base_image_path TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS views (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  page_id TEXT NOT NULL,
  payload_id INTEGER NOT NULL,
  auth_tag INTEGER NOT NULL,
  seed TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id),
  FOREIGN KEY(page_id) REFERENCES pages(id)
);

CREATE INDEX IF NOT EXISTS idx_views_payload_id ON views(payload_id);
CREATE INDEX IF NOT EXISTS idx_views_user_page ON views(user_id, page_id);

CREATE TABLE IF NOT EXISTS render_logs (
  id TEXT PRIMARY KEY,
  view_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  page_id TEXT NOT NULL,
  rendered_at TEXT NOT NULL,
  renderer_version TEXT NOT NULL,
  client_ip_hash TEXT,
  user_agent_hash TEXT
);
"""


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA)
        con.commit()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    init_db()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()
